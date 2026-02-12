from flask import Blueprint, jsonify, request, url_for, current_app, abort, flash
from flask_socketio import SocketIO
import eventlet
import serial
import os, json, re, time
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests
from lib.motion_planner import gantry_planner as gp

plugin_blueprint = Blueprint('spatial',
                __name__,
                url_prefix='/spatial')

panel_association = "Spatial"

scripts =["spatial.js"]

serial_reader_alias = None
serial_device_list = {}
linear_gantry_device_list = {}
app_root_path = None

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
    global serial_device_list, serial_reader_alias, linear_gantry_device_list
    global app_root_path

    serial_reader_alias = SerialReader
    app_root_path = app.root_path

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
        elif param["type"] == "linear_gantry_config":

            linear_gantry_device = gp.LinearGantryPlanner( limits = param["frame_limits_mm"], 
                            home_dirs = param["home_direction"] , 
                            mm_per_revs = param["mm_per_rev"], 
                            default_home_pose= param["default_home_pose"], 
                            max_speed =  param["max_linear_vel"], #in mm/s
                            )
            
            linear_gantry_device_list[param["associated_serial_device"]] = linear_gantry_device




def register_socket_handlers(socketio):
    @socketio.on("joystick_xyz")
    def joystick_xyz(msg):
        # print(msg)

        device = msg["device"]
        x = float(msg["x"]) *5 #convert to arbitrary scaling
        y = float(msg["y"]) *5 #convert to arbitrary scaling
        z = float(msg["z"]) *5 #convert to arbitrary scaling

        out =linear_gantry_device_list[device].move([x,y,z], 80)

        # out = motion_platform_planner.move([x,y,z], 5)

        if out:
            serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
            time.sleep(0.01)
            serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
            time.sleep(0.01)
    
    @socketio.on("moveto_xyzv")
    def move_to_xyz(msg):
        print(msg)
        device =msg["device"]
        x = float(msg["x"]) 
        y = float(msg["y"]) 
        z = float(msg["z"])
        vel = float(msg["v"])
        out =linear_gantry_device_list[device].move_to([x,y,z], vel)
        if out:
            print(out)

            serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
            time.sleep(0.01)
            serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")


    return "joystick_xyz, moveto_xyzv"


def reload_routine(socketio, app):
    global serial_device_list, serial_reader_alias, linear_gantry_device_list

    # Kill serial devices
    for device in serial_device_list.values():
        device.kill()
    serial_device_list.clear()
    linear_gantry_device_list.clear()

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
    output_data["pose_data"] = linear_gantry_device_list[device].get_current_pose()

    return jsonify(output_data)  # Return JSON response



@plugin_blueprint.route("/motion_routine/<string:device>", methods=["GET", "POST"])
def motion_routine(device):

    if device not in serial_device_list:
        abort(404)

    config_file = load_config(app_root_path, "panels.json")[panel_association]['config']['set_to']
    config_params = load_config(app_root_path, config_file)
    motion_config = None
    motion_routine = None
    motion_param = None

    for param, config in config_params.items():
        if config["type"] == "linear_gantry_config" and config["associated_serial_device"]==device:
            motion_config = config
            motion_routine = config["motion_routine"]
            motion_param = param

    if motion_config is None or motion_routine is None:
        abort(404)

    if request.method == "POST":
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON received"}), 400
        

        config_params[motion_param]["motion_routine"] =  data["points"]
        
        # Save the updated config back to JSON
        with open(os.path.join(app_root_path, "config", config_file), "w") as file:
            json.dump(config_params, file, indent=4)
        
        ## Note: may potentially need to include reload plugin routine, pending testing
        # reload_plugins(app,socketio)
        flash(f"{device} motion routine update in {config_file}", "success")
        
        return jsonify({
                "status": "ok",
                "file": config_file,
                "points_saved": len(data["points"])
            })
        
    #     # Process form submission
    #     ## Typically u can add configs that are a generic text or number type, and create parameters label, type, value_type, and set_to for quick, but if you have plugin specific parameters, you will need to add to this code under type param  
    #     new_config = config_params
    #     for key, params in config_params.items():

    #         ## Generic Parameter config through value_type 
    #         if "value_type" in params:
    #             user_input = request.form.get(key, "")

    #             if params["value_type"] == "number":
    #                 new_config[key]["set_to"] = int(user_input)
    #             else:
    #                 new_config[key]["set_to"] = user_input

    #         ## Plugin Specific Configuration parameters
    #         if params["type"] == "kasa_plug":
    #             new_config[key]["auto_enabled"]=  True if request.form.get(f"{key}_auto") =="on" else False 
    #         elif params["type"] == "serial_port":
    #             new_config[key]["baud_rate"]=  int(request.form.get(f"{key}_baudrate"))
    #             new_config[key]["timeout"]=  int(request.form.get(f"{key}_timeout"))
    #             new_config[key]["poll_rate"]=  float(request.form.get(f"{key}_poll"))
    #         elif params["type"] == "linear_gantry_config":
    #             new_config[key]["associated_serial_device"] = request.form.get(f"{key}_associated_serial_device")

    #             new_config[key]["frame_limits_mm"]["x"] = float(request.form.get(f"{key}_frame_limit_mm_x"))
    #             new_config[key]["frame_limits_mm"]["y"] = float(request.form.get(f"{key}_frame_limit_mm_y"))
    #             new_config[key]["frame_limits_mm"]["z"] = float(request.form.get(f"{key}_frame_limit_mm_z"))
                
    #             new_config[key]["mm_per_rev"]["x"] = float(request.form.get(f"{key}_mm_per_rev_x"))
    #             new_config[key]["mm_per_rev"]["y"] = float(request.form.get(f"{key}_mm_per_rev_y"))
    #             new_config[key]["mm_per_rev"]["z"] = float(request.form.get(f"{key}_mm_per_rev_z"))

    #             new_config[key]["home_direction"]["x"] = int(request.form.get(f"{key}_home_direction_x"))
    #             new_config[key]["home_direction"]["y"] = int(request.form.get(f"{key}_home_direction_y"))
    #             new_config[key]["home_direction"]["z"] = int(request.form.get(f"{key}_home_direction_z"))

    #             new_config[key]["default_home_pose"]["x"] = float(request.form.get(f"{key}_default_home_pose_x"))
    #             new_config[key]["default_home_pose"]["y"] = float(request.form.get(f"{key}_default_home_pose_y"))
    #             new_config[key]["default_home_pose"]["z"] = float(request.form.get(f"{key}_default_home_pose_z"))
                
    #             new_config[key]["max_linear_vel"] = float(request.form.get(f"{key}_max_linear_vel"))
                
                

    #     # Save the updated config back to JSON
    #     with open(os.path.join(app.root_path, "config", config_file), "w") as file:
    #         json.dump(new_config, file, indent=4)

    #     reload_plugins(app,socketio)
    #     flash(f"{panel} configuration saved successfully!", "success")
    #     return redirect(url_for("configure", panel=panel))


    return jsonify(motion_routine)
