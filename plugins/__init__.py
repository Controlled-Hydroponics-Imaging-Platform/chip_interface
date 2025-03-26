import os
import importlib
from datetime import datetime, time
from time import sleep
import eventlet
import threading
import serial
strfmt= "%Y-%m-%d %H:%M:%S"

module_list={}

class ControlScheduler:
    def __init__(self, socketio, device_name, device_ip, schedule_config, control_callback, check_state_callback):
        self.task = None
        self.state_sync_task = None
        self.socketio = socketio
        self._running = True
        self.device_name = device_name
        self.device_ip = device_ip
        self.schedule = schedule_config  # Pass the schedule JSON list here
        self.control_callback = control_callback  # Callable to toggle plug ON/OFF
        self.check_state_callback = check_state_callback
        self.last_state = False

    def start(self):
        self.kill()  # Always clean start
        print(f"✅ Starting control scheduler for {self.device_name}")
        self._running = True

        self.task = threading.Thread(target=self.control_schedule, daemon=True)
        self.state_sync_task = threading.Thread(target=self.sync_state_loop, daemon=True)

        self.task.start()
        self.state_sync_task.start()


    def kill(self):
        print(f"🛑 Killing control scheduler for {self.device_name}")
        self._running = False  # Signal both loops to stop

        # Kill the control task
        if self.task:
            self.task.join(timeout=5)
            print(f"✅ Control loop for {self.device_name} killed")
            self.task = None

        # Kill the sync state task
        if self.state_sync_task:
            self.state_sync_task.join(timeout=5)
            print(f"✅ Sync state loop for {self.device_name} killed")
            self.state_sync_task = None

        print(f"✅ {self.device_name} fully stopped")

    def sync_state_loop(self):
        """Periodically fetches the real plug state."""
        try:
            while self._running:
                try:
                    with eventlet.Timeout(5, False):  # ✅ Optional timeout safety
                        real_state = self.check_state_callback(self.device_ip)
                        self.last_state = real_state

                        output_data = {
                                    "data": real_state,
                                    "timestamp": datetime.now().strftime(strfmt)
                                }
                        self.socketio.emit(f"{self.device_name}_control_update", output_data)
                        # print(f"🔄 Synced state: {self.device_name} is {'ON' if real_state else 'OFF'}")
                except Exception as e:
                    print(f"⚠️ Error syncing state for {self.device_name}: {e}")
                sleep(10)
        finally:
            print(f"✅ Sync loop fully exited for {self.device_name}")

    def control_schedule(self):
        try:
            while self._running:
                now = datetime.now()
                today = now.strftime("%A")
                current_time = now.time()
                # print(self.schedule)

                should_be_on = False
                for block in self.schedule:
                    if today in block.get("days", []):
                        start_time = self._parse_time(block.get("start"))
                        end_time = self._parse_time(block.get("end"))
                        if start_time and end_time and self._time_in_range(start_time, end_time, current_time):
                            should_be_on = True
                            break

                # print(should_be_on)
                
                # Only act if the state needs changing
                if should_be_on != self.last_state:
                    action = "ON" if should_be_on else "OFF"
                    print(f"🕒 [{now.strftime(strfmt)}] - {self.device_name} → {action}")
                    try:
                        self.control_callback(self.device_ip, should_be_on)
                        self.last_state = should_be_on  # ✅ Update assuming success
                    except Exception as e:
                        print(f"❌ Failed to toggle {self.device_name}: {e}")

                sleep(30)
        finally:
            print(f"✅ Schedule loop fully exited for {self.device_name}")

    def _parse_time(self, t_str):
        try:
            h, m = map(int, t_str.split(":"))
            return time(h, m)
        except (ValueError, TypeError):
            return None

    def _time_in_range(self, start, end, now_time):
        if start <= end:
            return start <= now_time <= end
        else:
            # Handles overnight schedules (start: 22:00, end: 06:00)
            return now_time >= start or now_time <= end
        
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

        self.kill()

        print(f"🚀 Starting serial reader task for {self.device_name}")
        self._running = True
        self.task = threading.Thread(target=self.read_serial_socket, daemon=True)
        self.task.start()

    def kill(self):
        
        print(f"🛑 Killing task for {self.device_name}")
        self._running = False  # ✅ Signal loop to stop
        if self.task:
            self.task.join(timeout=5)
            self.task = None
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

                            sleep(self.poll_rate)
                            
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
                        sleep(5)

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
            if hasattr(module, 'register_control_scheduler_sockets'):
                module.register_control_scheduler_sockets(ControlScheduler, socketio, app)
                print(f" * {module_name} Control Schedulers started")
            if hasattr(module, 'scripts'):
                for script in module.scripts: script_list.append(script)
                print(f" * {', '.join(script for script in module.scripts)} scripts will be loaded")

    return script_list

def reload_plugins(app, socketio):
    for module_name,module in module_list.items():
        if hasattr(module, 'reload_routine'):
            module.reload_routine(SerialReader, ControlScheduler, socketio, app)
            print(f"{module_name} plugins/sockets reloaded")
