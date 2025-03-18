import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, url_for, abort, request, jsonify, redirect, flash
from flask_socketio import SocketIO
import serial.tools.list_ports
import time
import json
import os


app = Flask(__name__)
app.secret_key = "supersecretkey" 
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

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


# Web interface Routing

@app.route("/")
def home():
    enabled_panels = {k: v for k,v in load_config("panels.json").items() if v.get("enabled",False)} # list of valid panels

    return render_template("index.html",panels=enabled_panels)

@app.route("/settings")
def settings():
    panels = load_config("panels.json")
    return render_template("settings.html",panels=panels)

@app.route("/configuration/<string:panel>", methods=["GET", "POST"])
def configure(panel):
    # config_file = request.args.get("config_file")
    enabled_panels = {k: v for k,v in load_config("panels.json").items() if v.get("enabled",False)} # list of valid panels

    if panel not in enabled_panels:
        abort(404)

    config_file=enabled_panels[panel]["config"]
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

        flash("Configuration saved successfully!", "success")
        return redirect(url_for("configure", panel=panel))


    return render_template("config.html", panel_name=panel, config_params=config_params, config_file=config_file)


# Simulated function to send real-time data
def send_sensor_data():
    while True:
        # Simulated sensor value (Replace with real serial data)
        # printer.write(b'M105\n')  # Example G-code for temperature
        # response = printer.readline().decode().strip()  # Read from serial
        response = "Temperature: " + str(round(20 + (5 * time.time() % 5), 2))  # Fake data
        
        socketio.emit("sensor_update", {"value": response})  # Send data to frontend
        eventlet.sleep(1)

@socketio.on("connect")
def handle_connect():
    print("Client connected")
    socketio.start_background_task(send_sensor_data)


@app.errorhandler(400)
def bad_request(error):
    return f"❌ Bad Request: {error.description}", 400

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)