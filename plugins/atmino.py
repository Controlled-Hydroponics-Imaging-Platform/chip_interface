from flask import Blueprint, jsonify, request, url_for, current_app
import os, json
from datetime import datetime
from time import sleep
strfmt= "%Y-%m-%d %H:%M:%S"
from lib.pi_data_storage_handler import database_handler as dh
from lib.data_aggregator.capture_registry import capture_registry

# topic_list = []
atmino_device = None
mqtt_bridge_alias = None
data_handler = None
last_seen_data = {}
active_experiment=None
panel_association = "Atmino"
experiment_panel_association = "Experiments" 
capture_name = "atmino_data"


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
    global mqtt_bridge_alias, atmino_device, data_handler, last_seen_data, active_experiment
    mqtt_bridge_alias = mqttBridge

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)

    atmino_device = mqttBridge(socketio, 
                               device_name="atmino", 
                               broker_host= config["mqtt_broker_address"]["set_to"], 
                               broker_port = int(config["mqtt_broker_port"]["set_to"]), 
                               topics=(config["mqtt_sub_topic"]["set_to"]), 
                               username=config["mqtt_user"]["set_to"], 
                               password=config["mqtt_pwd"]["set_to"], 
                               keepalive=60, 
                               reconnect_min=1, reconnect_max=30)
        
    atmino_device.start()
    capture_registry.register(name=capture_name, callback= capture_atmino_data)


    experiment_config_file = load_config(app.root_path, "panels.json")[experiment_panel_association]['config']['set_to']
    experiment_config = load_config(app.root_path, experiment_config_file)
    active_experiment = experiment_config["active_experiment"]["set_to"]

    if experiment_config["data_logging"]["set_to"]:
        data_handler = dh.SQLiteDataHandler(experiment_config["database_path"]["set_to"],dh.SENSORS_TABLE)
        data_handler.start(continuous_atmino_logging,routine_name="continuous_atmino_logging")
    
    last_seen_data = atmino_device.last_output

def reload_routine(socketio, app):
    global mqtt_bridge_alias,atmino_device, data_handler

    # Kill atmino devices
    atmino_device.kill()
    atmino_device = None

    # Kill datahandlers
    if data_handler:
        data_handler.kill_all()
        data_handler = None

    #de-register callback from capture_register
    capture_registry.deregister(capture_name)

    # Re-register
    register_mqtt_sockets(mqtt_bridge_alias, socketio, app)

def continuous_atmino_logging():
    global atmino_device, data_handler, last_seen_data, active_experiment

    data_out = atmino_device.last_output

    if data_out != last_seen_data:
        last_seen_data = data_out
        # print(data_out)

        sorted_data= {
            "experiment_id": active_experiment,
            "device_id": atmino_device.device_name,
            "sensor_type":"envirionment",
            "payload_json": json.dumps(data_out.get("data")),
            "timestamp": data_out.get("timestamp_utc")        
            }

        data_handler.insert("sensor_continuous",sorted_data)
    
def capture_atmino_data():
    global atmino_device, data_handler, active_experiment

    data_out = atmino_device.last_output

    sorted_data= {
            "data_table": "sensor_events",
            # "experiment_id": active_experiment,
            "device_id": atmino_device.device_name,
            "sensor_type":"envirionment",
            "payload_json": data_out.get("data"),
            "timestamp": data_out.get("timestamp_utc")        
            }
    
    return sorted_data

# SENSOR_CAPTURE_TABLE_CONTENT = """
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     capture_id TEXT NOT NULL,
#     device_id TEXT NOT NULL,
#     sensor_type TEXT NOT NULL,
#     payload_json TEXT NOT NULL,

#     FOREIGN KEY(capture_id) REFERENCES capture_events(capture_id)
# """

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
