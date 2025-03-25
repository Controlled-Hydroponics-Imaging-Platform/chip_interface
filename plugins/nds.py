from flask import Blueprint, jsonify, request, url_for
from flask_socketio import SocketIO
import eventlet
import serial
import os, json
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests

plugin_blueprint = Blueprint('nds',
                __name__,
                url_prefix='/nds')

panel_association = "NDS"

scripts =["nds.js"]

valid_sensors = ["Distance", "Water_Temp", "EC", "PH"]

serial_device_list = {}
control_schedule_list = {}


def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}


def process_nds_data(serial_output):
    data_dict = {}
    for item in serial_output.split(','):
        parts = item.strip().split(':', 1)
        if len(parts) == 2:
            key, value = parts
            key,unit = key.rsplit('_',1) if '_' in key else (key, "")

            if key not in valid_sensors:
                print(f"{key} is not a valid sensor")
            else:
                data_dict[key.strip()]= {"value": value.strip(), "unit": unit.strip()}

        else:
            print(f"⚠️ Skipping malformed item: '{item}'")
    return data_dict


def check_kasa_plug_status(device_ip):
    status_url = f"http://localhost:5000/kasa_plug/status?ip={device_ip}"
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
        state_str = "true" if state else "false"
        endpoint_url = f"http://localhost:5000/kasa_plug/set_plug?ip={device_ip}&state={state}"
        print(endpoint_url)
        # Send the POST request
        response = requests.post(endpoint_url)

        if response.ok:
            print(f"✅ {response.json().get('message')}")
        else:
            print(f"❌ Failed to set plug state: {response.text}")
    except Exception as e:
        print(f"❌ Error toggling plug {device_ip}: {e}")

def register_serial_sockets(SerialReader, socketio, app):
    global serial_device_list

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)

    for key,param in config.items():
        if param["type"] =="serial_port" and param['set_to']!="":
            serial_device = SerialReader( socketio, 
                                          device_name=key, 
                                          port=param["set_to"],
                                          baudrate=param["baud_rate"],
                                          timeout=param["timeout"], 
                                          process_raw_data=process_nds_data, 
                                          poll_rate=param["poll_rate"] 
                                        )
            
            serial_device.start()
            serial_device_list[serial_device.device_name]= serial_device

def register_control_scheduler_sockets(ControlScheduler, socketio, app):
    global control_schedule_list

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)
    
    for key,param in config.items():
        if param["type"] =="kasa_plug" and param['set_to']!="" and param['auto_enabled']:
            control_device = ControlScheduler( socketio,
                                               device_name=key, 
                                               device_ip=param['set_to'],
                                               schedule_config=param['schedule'], 
                                               control_callback=toggle_kasa_plug, 
                                               check_state_callback =check_kasa_plug_status
                                            )
            control_device.start()
            control_schedule_list[control_device.device_name]= control_device

                    

def reload_routine(SerialReader, ControlScheduler, socketio, app):
    global serial_device_list, control_schedule_list

    # Kill serial devices
    for device in serial_device_list.values():
        device.kill()
    serial_device_list.clear()

    # Kill control schedulers
    for device in control_schedule_list.values():
        device.kill()
    control_schedule_list.clear()

    # Re-register
    register_serial_sockets(SerialReader, socketio, app)
    register_control_scheduler_sockets(ControlScheduler, socketio, app)



# API
@plugin_blueprint.route("/serial_devices")
def get_serial_devices():
    output={}

    for name, device in serial_device_list.items():
        output[name]= {
            "port": device.port,
            "baudrate": device.baudrate
        }

    return jsonify(output)  # Return JSON response

@plugin_blueprint.route("/processed_data")
def get_serial_data():
    device = request.args.get("device")

    output_data = serial_device_list[device].last_output


    return jsonify(output_data)  # Return JSON response
