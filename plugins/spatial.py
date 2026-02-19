from flask import Blueprint, jsonify, request, url_for, current_app, abort, flash
from flask_socketio import SocketIO
import eventlet
import serial
import os, json, re, time
from datetime import datetime
strfmt= "%Y-%m-%d %H:%M:%S"
import requests
from lib.motion_planner import gantry_planner as gp
from lib.motion_planner import routine_coordinator


plugin_blueprint = Blueprint('spatial',
                __name__,
                url_prefix='/spatial')

panel_association = "Spatial"

scripts =["spatial.js"]

serial_reader_alias = None
serial_device_list = {}
linear_gantry_device_list = {}
device_routine_coordinator_list= {}
# data_handler_list = {}
app_root_path = None

###### Callbacks background and threaded processes: Serial proceses_driver_data, Routine scheduler gantry planner and data proc action callback(linear_gantry_routine_callback) 

def process_driver_data(raw_serial_output):
    """
    Processes the raw output from serial device of the chip motor_driver
    :param raw_serial_output: Example - [OUTPUT] z_limit(limit_switch):off y_limit(limit_switch):off x_limit(limit_switch):off x(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps), y(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps), z(StepperMotor):100.0000(rpm),+,0.00000(rev),0(steps),
    """
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


    #Parse standby mode
    standby_pattern = re.compile(r"([xyz])\(StepperMotor\):Standby\b")
    for axis in standby_pattern.findall(raw_serial_output):
        # You can change these defaults if you prefer
        data_dict[axis]["speed_rpm"] = "standby"
        data_dict[axis]["direction"] = "standby"
        data_dict[axis]["position_rev"] = "standby"
        data_dict[axis]["position_step"] = "standby"

    return data_dict

def linear_gantry_routine_callback(device):
    """
    Callback for routine scheduler
    Workflow: standby off > calibrate > while data and motion routine >  standby on
    """
    ## Standby off
    print(f"{device} action routine triggered")

    out = linear_gantry_device_list[device].standby(False)
    if out:
        serial_device_list[device].write(f"standby x,{out['config']['x']} y,{out['config']['y']} z,{out['config']['z']}")

    time.sleep(1)

    ## Calibrate
    out = linear_gantry_device_list[device].home(True)
    if out:
        serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
        time.sleep(0.01)
        serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
    print(f"{device}: calibrating")
    
    time.sleep(out["t_s"]*2)
    print(f"{device}: Done calibrating")

    ## While routine (Motion and data)
    while (res:=linear_gantry_device_list[device].next())[1]:
        out =res[0]
        
        if out:
            serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
            time.sleep(0.01)
            serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")

        print(f"moving to {out["target_pose"]}")
        time.sleep(out['t_s']*2)
        print(f"{device}: current pose{linear_gantry_device_list[device].get_current_pose()}")

        #### This is where the data protocol goes
    
    print(f"Finished Routine entering standby")

    ## Standby On
    out = linear_gantry_device_list[device].standby(True)
    if out:
        serial_device_list[device].write(f"standby x,{out['config']['x']} y,{out['config']['y']} z,{out['config']['z']}")

    next_trigger, _ = device_routine_coordinator_list[device].get_next_trigger_info()
    print(f"{device}: Done until {next_trigger}")


###### Utility Functions

def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}

###### Plugin Dependency and parameter loading functions 

def register_serial_sockets(SerialReader, socketio, app):
    global serial_device_list, serial_reader_alias, linear_gantry_device_list, device_routine_coordinator_list
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
            # Load Linear gantry planners
            linear_gantry_device = gp.LinearGantryPlanner( limits = param["frame_limits_mm"], 
                            home_dirs = param["home_direction"] , 
                            mm_per_revs = param["mm_per_rev"], 
                            default_home_pose= param["default_home_pose"], 
                            max_speed =  param["max_linear_vel"], #in mm/s
                            associated_device_name= param["associated_serial_device"]
                            )
            linear_gantry_device.load_motion_routine(param["motion_routine"])
            linear_gantry_device_list[param["associated_serial_device"]] = linear_gantry_device

            # Load routine coordinators
            device_routine_coordinator = routine_coordinator.RoutineHandler(lambda: linear_gantry_routine_callback(param["associated_serial_device"]),associated_device_name= param["associated_serial_device"])
            device_routine_coordinator.set_schedule(param["routine_schedule"])
            device_routine_coordinator_list[param["associated_serial_device"]]  = device_routine_coordinator


def register_socket_handlers(socketio):
    ## Socket activates and deactivates the routine schedulers
    @socketio.on("set_routine_state")
    def set_routine_state(msg):
        device =msg["device"]
        
        if msg["payload"] =="activate":
            device_routine_coordinator_list[device].start()
            out = linear_gantry_device_list[device].standby(True)
            if out:
                serial_device_list[device].write(f"standby x,{out['config']['x']} y,{out['config']['y']} z,{out['config']['z']}")

        elif msg["payload"] == "disactivate":
            device_routine_coordinator_list[device].kill()
            out = linear_gantry_device_list[device].standby(True)
            if out:
                serial_device_list[device].write(f"standby x,{out['config']['x']} y,{out['config']['y']} z,{out['config']['z']}")
            
    ## Socket parses commands and translates them into functions for motor driver
    @socketio.on("platform_command_parser")
    def platform_command_parser(msg):
        device =msg["device"]
        print(msg)

        if msg["command"]=="home_calibrate":
            out = linear_gantry_device_list[device].home(True)

            if out:
                serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
                time.sleep(0.01)
                serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
        
        elif msg["command"]=="home":
            out = linear_gantry_device_list[device].home()

            if out:
                serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
                time.sleep(0.01)
                serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
        
        elif msg["command"]=="standby":

            state = bool(msg["state"])
            out = linear_gantry_device_list[device].standby(state)

            if out:
                serial_device_list[device].write(f"standby x,{out['config']['x']} y,{out['config']['y']} z,{out['config']['z']}")

        elif msg["command"] == "move":
            x = float(msg["x"]) 
            y = float(msg["y"]) 
            z = float(msg["z"])
            vel = float(msg["v"])

            out =linear_gantry_device_list[device].move([x,y,z], vel)

            if out:
                serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
                time.sleep(0.01)
                serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
                time.sleep(0.01)

        elif msg["command"] == "move_to":
            x = float(msg["x"]) 
            y = float(msg["y"]) 
            z = float(msg["z"])
            vel = float(msg["v"])

            out =linear_gantry_device_list[device].move_to([x,y,z], vel)

            if out:
                serial_device_list[device].write(f"speed x,{out['q_dot']['x']} y,{out['q_dot']['y']} z,{out['q_dot']['z']}")
                time.sleep(0.01)
                serial_device_list[device].write(f"move x,{out['delta_q']['x']} y,{out['delta_q']['y']} z,{out['delta_q']['z']}")
                time.sleep(0.01)
        else:
            print("command not resigstered to socket callback")

    return "platform_command_parser, set_routine_state"


def reload_routine(socketio, app):
    global serial_device_list, serial_reader_alias, linear_gantry_device_list

    # Kill serial devices
    for device in serial_device_list.values():
        device.kill()
    serial_device_list.clear()
    
    # Kill any running routine devices
    for device in device_routine_coordinator_list.values():
        device.kill()
    device_routine_coordinator_list.clear()

    linear_gantry_device_list.clear()

    # Re-register
    register_serial_sockets(serial_reader_alias, socketio, app)


###### API: /spatial/...

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
    output_data["schedule_data"] = device_routine_coordinator_list[device].get_output()
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
        ## reload motion_routine
        # linear_gantry_device_list[device].kill()
        linear_gantry_device_list[device].load_motion_routine(config_params[motion_param]["motion_routine"])

        flash(f"{device} motion routine update in {config_file}", "success")
        
        return jsonify({
                "status": "ok",
                "file": config_file,
                "points_saved": len(data["points"])
            })

    return jsonify(motion_routine)


@plugin_blueprint.route("/routine_schedule/<string:device>", methods=["GET", "POST"])
def routine_schedule(device):

    if device not in serial_device_list:
        abort(404)

    config_file = load_config(app_root_path, "panels.json")[panel_association]['config']['set_to']
    config_params = load_config(app_root_path, config_file)
    schedule_config = None
    routine_schedule = None
    schedule_param = None

    for param, config in config_params.items():
        if config["type"] == "linear_gantry_config" and config["associated_serial_device"]==device:
            schedule_config = config
            routine_schedule = config["routine_schedule"]
            schedule_param= param

    if schedule_config is None or routine_schedule is None:
        abort(404)

    if request.method == "POST":
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON received"}), 400
        

        config_params[schedule_param]["routine_schedule"] =  data["schedule"]
        
        # Save the updated config back to JSON
        with open(os.path.join(app_root_path, "config", config_file), "w") as file:
            json.dump(config_params, file, indent=4)
        
        ## Note: may potentially need to include reload plugin routine, pending testing
        # reload_plugins(app,socketio)
        ## reload schedule
        device_routine_coordinator_list[device].set_schedule(config_params[schedule_param]["routine_schedule"])

        flash(f"{device} motion routine update in {config_file}", "success")
        
        return jsonify({
                "status": "ok",
                "file": config_file,
            })

    return jsonify(routine_schedule)
