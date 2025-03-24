import os
import importlib
from datetime import datetime
import eventlet
import serial
strfmt= "%Y-%m-%d %H:%M:%S"

module_list={}

class SerialReader:
    def __init__(self, socketio, device_name, port, baudrate, timeout, process_raw_data, poll_rate):
        self.task = None
        self.device_name = device_name
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.process_raw_data = process_raw_data
        self.poll_rate = poll_rate
        self.socketio = socketio
        self.last_output = {}
        self._running = True  # ✅ Control loop for graceful shutdown

    def start(self):
        if self.task:
            print("🛑 Stopping existing task")
            self.kill()

        print(f"🚀 Starting serial reader task for {self.device_name}")
        self._running = True
        self.task = eventlet.spawn(self.read_serial_socket)

    def kill(self):
        if self.task:
            print(f"🛑 Killing task for {self.device_name}")
            self._running = False  # ✅ Signal loop to stop
            self.task.kill()
        print(f"✅ {self.device_name} stopped")

    def read_serial_socket(self):
        try:
            while self._running:
                try:
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "connecting", "device": self.port})
                    print(f"🔌 Connecting to serial {self.device_name} ({self.port})...")
                    ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

                    ser.reset_input_buffer()
                    print(f"✅ {self.device_name} ({self.port}): Serial connection established")
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "connected", "device": self.port})

                    # Discard first few lines to sync
                    for _ in range(5):
                        try:
                            ser.readline()
                        except (serial.SerialException, OSError) as e:
                            print(f"⚠️ Sync error: {e}")
                            break  # Will trigger reconnect

                    # Main reading loop
                    while self._running:
                        try:
                            if ser.in_waiting > 0:
                                raw_data = None
                                while ser.in_waiting:
                                    raw_data = ser.readline().decode('utf-8', errors='ignore').strip()

                                if not raw_data:
                                    print(f"⚠️ Skipping bad data: {raw_data}")
                                    continue

                                processed_data = self.process_raw_data(raw_data)
                                output_data = {
                                    "data": processed_data,
                                    "timestamp": datetime.now().strftime(strfmt)
                                }
                                self.socketio.emit(f"{self.device_name}_sensor_update", output_data)
                                self.last_output = output_data

                            eventlet.sleep(self.poll_rate)

                        except (serial.SerialException, OSError) as e:
                            print(f"❌ Serial read error: {e}")
                            break  # Break inner loop to reconnect

                except (serial.SerialException, OSError) as e:
                    print(f"❌ Connection failed: {e}")
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "disconnected", "device": self.port})

                finally:
                    try:
                        ser.close()
                        print(f"⚠️ {self.device_name} Serial connection closed")
                    except:
                        pass

                    if self._running:
                        print("🔄 Reconnecting in 5 seconds...")
                        eventlet.sleep(5)

        except eventlet.greenlet.GreenletExit:
            print(f"✅ Serial reader for {self.device_name} terminated")



def load_all_plugins(app, socketio):
    global module_list
    script_list = []
    plugin_dir = os.path.dirname(__file__)
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            module = importlib.import_module(f'plugins.{module_name}')
            module_list[module_name] = module
            if hasattr(module, 'plugin_blueprint'):
                app.register_blueprint(module.plugin_blueprint)
                print(f" * Registered plugin: {module_name}")
            if hasattr(module, 'register_serial_sockets'):
                module.register_serial_sockets(SerialReader, socketio, app)
                print(f" * {module_name} serial sockets started")
            if hasattr(module, 'scripts'):
                for script in module.scripts: script_list.append(script)
                print(f" * {', '.join(script for script in module.scripts)} scripts will be loaded")

    return script_list

def reload_plugins(app, socketio):
    for module_name,module in module_list.items():
        if hasattr(module, 'reload_routine'):
            module.reload_routine(SerialReader, socketio, app)
            print(f"{module_name} plugins/sockets reloaded")
