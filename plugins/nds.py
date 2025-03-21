from flask import Blueprint
from flask_socketio import SocketIO
import eventlet
import serial
import os, json

plugin_blueprint = Blueprint('nds',
                __name__,
                url_prefix='/nds')

panel_association = "NDS"

scripts =["nds.js"]

def process_nds_data(serial_output):
    data_dict = {}
    for item in serial_output.split(','):
        parts = item.strip().split(':', 1)
        if len(parts) == 2:
            key, value = parts
            data_dict[key.strip()] = value.strip()
        else:
            print(f"⚠️ Skipping malformed item: '{item}'")
    return data_dict


def register_sockets(socketio, app):

    def load_config(config_file):
        config_path = os.path.join(app.root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}
        
    panel_config = load_config("panels.json")[panel_association]
    config = load_config(panel_config['config']['set_to'])

    port, baud_rate, timeout = config['serial_port']['set_to'], config['baud_rate']['set_to'], config['timeout']['set_to']

    def read_serial_nds():
        while True:
            try:
                socketio.emit("nds_status_update", {"status": "connecting", "device": port})
                print("🔌 Attempting to connect to serial device...")
                ser = serial.Serial(port=port, baudrate=baud_rate, timeout=timeout)
                ser.reset_input_buffer()
                print("✅ Serial connection established")
                socketio.emit("nds_status_update", {"status": "connected", "device": port})

                # Discard first few lines to sync
                for _ in range(5):
                    try:
                        ser.readline()
                    except (serial.SerialException, OSError) as e:
                        print(f"⚠️ Error during sync: {e}")
                        break  # Will trigger outer retry

                # Main reading loop
                while True:
                    try:
                        if ser.in_waiting > 0:
                            raw_data=None
                            while ser.in_waiting:
                                raw_data = ser.readline().decode('utf-8', errors='ignore').strip() #This loop clears the buffered data to get the latest value instead of displaying the next backlogged 
                            
                            if not raw_data or 'Distance_mm' not in raw_data:
                                print(f"⚠️ Skipping bad data: {raw_data}")
                                continue
                            processed_data = process_nds_data(raw_data)
                            socketio.emit("nds_sensor_update", processed_data)

                        eventlet.sleep(3) # 3 seems to be a good delay for proper buffering

                    except (serial.SerialException, OSError) as e:
                        print(f"❌ Serial read error: {e}")
                        # socketio.emit("nds_status_update", {"status": "disconnected"})
                        break  # Breaks inner loop, triggers reconnect

            except (serial.SerialException, OSError) as e:
                print(f"❌ Serial connection failed: {e}")
                socketio.emit("nds_status_update", {"status": "disconnected", "device": port})

                # Always try to close cleanly
                try:
                    ser.close()
                    print("⚠️ Serial connection closed")
                except:
                    pass

                print("🔄 Attempting to reconnect in 5 seconds...")
                eventlet.sleep(5)  # Wait and try reconnect

    socketio.start_background_task(read_serial_nds)


@plugin_blueprint.route('/hello')
def hello():
    return "Hello from My Plugin!"