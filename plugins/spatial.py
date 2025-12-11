from flask import Blueprint, jsonify, request, url_for, current_app
from flask_socketio import SocketIO
import eventlet
import serial
import os, json, re
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests

plugin_blueprint = Blueprint('spatial',
                __name__,
                url_prefix='/spatial')

panel_association = "Spatial"


serial_reader_alias = None
serial_device_list = {}

def process_driver_data(raw_serial_output):
    # Example raw input: [OUTPUT] z_limit(limit_switch):off y_limit(limit_switch):off x_limit(limit_switch):off x(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps), y(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps), z(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps),
    data_dict = {
        axis:{"limit_switch_state": None,
              "speed_rpm": None,
              "direction": None,
              "position_rev": None,
              "position_step": None}
        for axis in ("x", "y", "z")
         
    }
    # Parse limit switches
    limit_pattern = re.compile(r"([xyz])_limit\(limit_switch\):(\w+)")
    for axis, state in limit_pattern.findall(raw_serial_output):
        data_dict[axis]["limit_switch_state"] = state

    # Parse stepper motor blocks
    motor_pattern = re.compile(
        r"([xyz])\(StepperMotor\):"
        r"(-?\d+(?:\.\d+)?)\(rpm\),"   # speed_rpm: optional -, int or float
        r"([+-]),"
        r"(-?\d+(?:\.\d+)?)\(rev\),"   # position_rev
        r"(-?\d+)\(steps\)"            # position_step
    )

    for axis, rpm, direction, rev, steps in motor_pattern.findall(raw_serial_output):
        data_dict[axis]["speed_rpm"] = float(rpm)
        data_dict[axis]["direction"] = direction
        data_dict[axis]["position_rev"] = float(rev)
        data_dict[axis]["position_step"] = int(steps)


    #Parse stanby mode
    standby_pattern = re.compile(r"([xyz])\(StepperMotor\):Standby\b")
    for axis in standby_pattern.findall(raw_serial_output):
        # You can change these defaults if you prefer
        data_dict[axis]["speed_rpm"] = "standby"
        data_dict[axis]["direction"] = "standby"
        data_dict[axis]["position_rev"] = "standby"
        data_dict[axis]["position_step"] = "standby"

    return data_dict


def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}

def register_serial_sockets(SerialReader, socketio, app):
    global serial_device_list, serial_reader_alias

    serial_reader_alias = SerialReader

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)

    for key,param in config.items():
        if param["type"] =="serial_port" and param['set_to']!="":
            serial_device = SerialReader( socketio, 
                                          device_name=key, 
                                          port=param["set_to"],
                                          baudrate=param["baud_rate"],
                                          timeout=param["timeout"], 
                                          process_raw_data=process_driver_data, 
                                          poll_rate=param["poll_rate"] 
                                        )
            
            serial_device.start()
            serial_device_list[serial_device.device_name]= serial_device

# def reload_routine(socketio, app):
def reload_routine(socketio, app):
    global serial_device_list, serial_reader_alias

    # Kill serial devices
    for device in serial_device_list.values():
        device.kill()
    serial_device_list.clear()

    # Re-register
    register_serial_sockets(serial_reader_alias, socketio, app)


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