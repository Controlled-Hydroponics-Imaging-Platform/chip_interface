import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, url_for, abort, request, jsonify, redirect, flash
from flask_socketio import SocketIO
import serial.tools.list_ports
import time
import json
import os
from plugins import load_all_plugins

app = Flask(__name__)
app.secret_key = "supersecretkey" 
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

script_list = load_all_plugins(app,socketio)

def load_config(config_file):
    config_path = os.path.join(app.root_path, "config", config_file)  # Correct path
    try:
        with open(config_path, "r") as file:
            return json.load(file)  # Load JSON as a dictionary
    except json.JSONDecodeError as e:
        print(f"🚨 JSON Error: {e}")
        return {}

def get_serial_ports():
    ports = serial.tools.list_ports.comports()  # Get all serial ports
    return [{"device": port.device, "description": port.description} for port in ports]

# API
@app.route("/get_serial_ports")
def get_ports():
    return jsonify(get_serial_ports())  # Return JSON response

@app.route("/plugin_scripts")
def get_plugin_scripts():
    return jsonify(script_list)  # Return JSON response


# Web interface Routing

@app.route("/")
def home():
    enabled_panels = {k: v for k,v in load_config("panels.json").items() if v["enabled"].get("set_to",False)} # list of valid panels

    return render_template("index.html",panels=enabled_panels)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    panels = load_config("panels.json")

    if request.method == "POST":
        new_settings = panels
        panel_submitted = request.form.get('panel_name')

        # Process form submission
        for key, settings in panels[panel_submitted].items():
            user_input = request.form.get(f"{panel_submitted}_{key}", "")
            print(user_input)

            if settings["value_type"] == "number":
                new_settings[panel_submitted][key]["set_to"]  = int(user_input)
            elif settings["value_type"] == "boolean":
                new_settings[panel_submitted][key]["set_to"]  = True if user_input =="on" else False
            else:
                new_settings[panel_submitted][key]["set_to"] = user_input


        # Save the updated config back to JSON
        with open(os.path.join(app.root_path, "config", "panels.json"), "w") as file:
            json.dump(new_settings, file, indent=4)

        flash(f"{panel_submitted} panel settings saved successfully!", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html",panels=panels)

@app.route("/configuration/<string:panel>", methods=["GET", "POST"])
def configure(panel):
    # config_file = request.args.get("config_file")
    enabled_panels = {k: v for k,v in load_config("panels.json").items() if v["enabled"].get("set_to",False)} # list of valid panels


    if panel not in enabled_panels:
        abort(404)

    config_file=enabled_panels[panel]["config"]["set_to"]
    config_params=load_config(config_file)

    if request.method == "POST":
        # Process form submission
        new_config = config_params
        for key, params in config_params.items():
            user_input = request.form.get(key, "")

            if params["value_type"] == "number":
                new_config[key]["set_to"] = int(user_input)
            else:
                new_config[key]["set_to"] = user_input


        # Save the updated config back to JSON
        with open(os.path.join(app.root_path, "config", config_file), "w") as file:
            json.dump(new_config, file, indent=4)

        flash(f"{panel} configuration saved successfully!", "success")
        return redirect(url_for("configure", panel=panel))


    return render_template("config.html", panel_name=panel, config_params=config_params, config_file=config_file)


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    # socketio.start_background_task(send_sensor_data)


@app.errorhandler(400)
def bad_request(error):
    return f"❌ Bad Request: {error.description}", 400

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)