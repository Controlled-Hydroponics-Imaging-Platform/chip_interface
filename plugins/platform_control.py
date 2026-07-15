from flask import Blueprint, jsonify, request, url_for, current_app
import os, json
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests

plugin_blueprint = Blueprint('platform_control',
                __name__,
                url_prefix='/platform_control')

panel_association = "Platform_Control"

scripts =["platform_control.js"]

host_url=None
control_schedule_list = {}

control_scheduler_alias = None


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

                    

# def reload_routine(SerialReader, ControlScheduler, socketio, app):
def reload_routine(socketio, app):
    global control_schedule_list, control_scheduler_alias

    # Kill control schedulers
    for device in control_schedule_list.values():
        device.kill()
    control_schedule_list.clear()

    # Re-register
    register_control_scheduler_sockets(control_scheduler_alias, socketio, app)



# API
@plugin_blueprint.route("/processed_data")
def get_serial_data():
    device = request.args.get("device")

    # output_data = serial_device_list[device].last_output


    return jsonify(output_data)  # Return JSON response
