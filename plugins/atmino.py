from flask import Blueprint, jsonify, request, url_for, current_app
import os, json
from flask_socketio import SocketIO
import eventlet
import paho.mqtt.client as mqtt
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"


topic_list = []

plugin_blueprint = Blueprint('atmino',
                __name__,
                url_prefix='/atmino')

panel_association = "NDS"

scripts =["nds.js"]


def on_connect(client, userdata, flags, rc):
     print("Connected to MQTT broker:")
     



# def process_atmino_data(topic_output):
#     data_dict = {}
#     for item in topic_output.split(','):
#         parts = item.strip().split(':', 1)
#         if len(parts) == 2:
#             key, value = parts
#             key,unit = key.rsplit('_',1) if '_' in key else (key, "")

#             if key not in valid_sensors:
#                 print(f"{key} is not a valid sensor")
#             else:
#                 data_dict[key.strip()]= {"value": value.strip(), "unit": unit.strip()}

#         else:
#             print(f"⚠️ Skipping malformed item: '{item}'")
#     return data_dict



def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}


# def register_mqtt_sockets(SerialReader, socketio, app):
#     global serial_device_list

#     config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
#     config = load_config(app.root_path, config_file)

#     for key,param in config.items():
#         if param["type"] =="serial_port" and param['set_to']!="":
#             serial_device = SerialReader( socketio, 
#                                           device_name=key, 
#                                           port=param["set_to"],
#                                           baudrate=param["baud_rate"],
#                                           timeout=param["timeout"], 
#                                           process_raw_data=process_nds_data, 
#                                           poll_rate=param["poll_rate"] 
#                                         )
            
#             serial_device.start()
#             serial_device_list[serial_device.device_name]= serial_device



# API
@plugin_blueprint.route("/topics")
def get_topic():
    output={}
    counter=0;

    for topic in topic_list:
        output = {
            f"topic {counter}": topic
        }
        counter+=1

    return jsonify(output)  # Return JSON response

@plugin_blueprint.route("/processed_data")
def get_serial_data():
    device = request.args.get("device")

    output_data = serial_device_list[device].last_output


    return jsonify(output_data)  # Return JSON response
