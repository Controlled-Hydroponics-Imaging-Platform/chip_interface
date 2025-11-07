from flask import Blueprint, jsonify, request, url_for, current_app
import os, json
from flask_socketio import SocketIO
import eventlet
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"

# topic_list = []
atmino_device = None
mqtt_bridge_alias = None
panel_association = "Atmino"


plugin_blueprint = Blueprint('atmino',
                __name__,
                url_prefix='/atmino')

scripts =["atmino.js"]

def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}


def register_mqtt_sockets(mqttBridge, socketio, app):
    global mqtt_bridge_alias, atmino_device
    mqtt_bridge_alias = mqttBridge

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)

    atmino_device = mqttBridge(socketio, 
                               device_name="atmino1", 
                               broker_host= config["mqtt_broker_address"]["set_to"], 
                               broker_port = int(config["mqtt_broker_port"]["set_to"]), 
                               topics=(config["mqtt_sub_topic"]["set_to"]), 
                               username=config["mqtt_user"]["set_to"], 
                               password=config["mqtt_pwd"]["set_to"], 
                               keepalive=60, 
                               reconnect_min=1, reconnect_max=30)
    
    atmino_device.start();

def reload_routine(socketio, app):
    global mqtt_bridge_alias,atmino_device

    # Kill atmino devices
    atmino_device.kill()
    atmino_device = None

    # Re-register
    register_mqtt_sockets(mqtt_bridge_alias, socketio, app)
 

# API
# @plugin_blueprint.route("/topics")
# def get_topic():
#     output={}
#     counter=0;

#     for topic in topic_list:
#         output = {
#             f"topic {counter}": topic
#         }
#         counter+=1

#     return jsonify(output)  # Return JSON response

@plugin_blueprint.route("/processed_data")
def get_mqtt_data():
    # device = request.args.get("device")

    output_data = atmino_device.last_output


    return jsonify(output_data)  # Return JSON response
