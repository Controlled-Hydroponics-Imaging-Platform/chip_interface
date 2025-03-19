from flask import Blueprint
from flask_socketio import SocketIO
import eventlet
import serial
import os, json

plugin_blueprint = Blueprint('nds',
                __name__,
                template_folder='templates',
                static_folder='static',
                url_prefix='/nds')

panel_association = "NDS"


def start_sockets(socketio, app):


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
        ser = serial.Serial(port=port, baudrate=baud_rate, timeout=timeout)

        while True:
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                socketio.emit("sensor_update", {"value": response})

            eventlet.sleep(1)

    socketio.start_background_task(read_serial_nds)
    




@plugin_blueprint.route('/hello')
def hello():
    return "Hello from My Plugin!"