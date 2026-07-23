from flask import Blueprint, jsonify, request, url_for, current_app
import os, json
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests
from lib.pi_data_storage_handler import database_handler as dh
from lib.data_aggregator.capture_registry import capture_registry


plugin_blueprint = Blueprint('platform_control',
                __name__,
                url_prefix='/platform_control')

panel_association = "Platform_Control"
experiment_panel_association = "Experiments" 

scripts =["platform_control.js"]

host_url=None
control_schedule_list = {}

control_scheduler_alias = None

data_handler = None
last_seen_data = {}
active_experiment=None




def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}



def check_kasa_plug_status(device_ip):

    status_url = f"{host_url}kasa_plug/status?ip={device_ip}"
    try:
        response = requests.get(status_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("state", False)
        else:
            print(f"⚠️ Failed to get status for {device_ip}: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"⚠️ Error checking status for {device_ip}: {e}")
        return False

def toggle_kasa_plug(device_ip, state):
    try:
        endpoint_url = f"{host_url}kasa_plug/set_plug?ip={device_ip}&state={state}"
        # print(endpoint_url)
        # Send the POST request
        response = requests.post(endpoint_url)

        if response.ok:
            print(f"✅ {response.json().get('message')}")
        else:
            print(f"❌ Failed to set plug state: {response.text}")
    except Exception as e:
        print(f"❌ Error toggling plug {device_ip}: {e}")


def register_control_scheduler_sockets(ControlScheduler, socketio, app):
    global control_schedule_list
    global host_url 
    global control_scheduler_alias
    global data_handler, active_experiment, last_seen_data


    control_scheduler_alias = ControlScheduler

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)
    host_url= app.config['BASE_URL']
    
    for key,param in config.items():
        if param["type"] =="kasa_plug" and param['set_to']!="" and param['auto_enabled']:
            print(key)
            control_device = ControlScheduler( 
                                               socketio,
                                               device_name=key, 
                                               device_ip=param['set_to'],
                                               schedule_config=param['schedule'], 
                                               control_callback=toggle_kasa_plug, 
                                               check_state_callback =check_kasa_plug_status
                                            )
            control_device.start()
            control_schedule_list[control_device.device_name]= control_device
    
    experiment_config_file = load_config(app.root_path, "panels.json")[experiment_panel_association]['config']['set_to']
    experiment_config = load_config(app.root_path, experiment_config_file)
    active_experiment = experiment_config["active_experiment"]["set_to"]

    if experiment_config["data_logging"]["set_to"]:
        data_handler = dh.SQLiteDataHandler(experiment_config["database_path"]["set_to"],dh.SCHEDULED_EVENTS_CONT_TABLE)
        data_handler.start(continuous_platform_control_logging,routine_name="continuous_platform_control_logging")

    for device_id, control_device in control_schedule_list.items():
        #register dataoutput callback to capture_registry
        capture_registry.register(f"{device_id}_data", lambda device_id=device_id: capture_platform_control_data(device_id))

        #get the last output
        data =control_device.get_last_output()
        last_seen_data[device_id] = data                

# def reload_routine(SerialReader, ControlScheduler, socketio, app):
def reload_routine(socketio, app):
    global control_schedule_list, control_scheduler_alias
    global data_handler

    # Kill control schedulers
    for device_id, device in control_schedule_list.items():
        device.kill()
        #deregister capture register callbacks
        capture_registry.deregister(f"{device_id}_data")
    control_schedule_list.clear()

    # Kill datahandlers
    if data_handler:
        data_handler.kill_all()
        data_handler = None


    # Re-register
    register_control_scheduler_sockets(control_scheduler_alias, socketio, app)


def continuous_platform_control_logging():
    global control_schedule_list, data_handler, last_seen_data, active_experiment

    # output_data = {}

    for device_id, control_device in control_schedule_list.items():
        data_out =control_device.get_last_output()

        # output_data[device_name] = data


        if data_out != last_seen_data[device_id]:
            last_seen_data[device_id] = data_out
            # print(data_out)

            sorted_data= {
                "experiment_id": active_experiment,
                "device_id": device_id,
                "event_type": device_id,
                "status": data_out.get("data"),
                "schedule_json": json.dumps(data_out.get("schedule")),
                "timestamp": data_out.get("timestamp_utc")        
                }

            data_handler.insert("scheduled_events_continuous",sorted_data)

def capture_platform_control_data(device_id):
    global control_schedule_list, data_handler, last_seen_data, active_experiment

    control_device = control_schedule_list[device_id]
    data_out = control_device.get_last_output()


    sorted_data= {
                "data_table": "scheduled_events",
                # "experiment_id": active_experiment,
                "device_id": device_id,
                "event_type": device_id,
                "status": data_out.get("data"),
                "schedule_json": json.dumps(data_out.get("schedule")),
                "timestamp": data_out.get("timestamp_utc")         
                }
        
    return sorted_data

# API
@plugin_blueprint.route("/processed_data")
def get_control_data():
    # device = request.args.get("device")
    output_data = {}

    for device_name, control_device in control_schedule_list.items():
        data =control_device.get_last_output()

        output_data[device_name] = data

    return jsonify(output_data)  # Return JSON response
