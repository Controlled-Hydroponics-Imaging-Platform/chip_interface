import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, url_for, abort
from flask_socketio import SocketIO
import serial
import time
import json
import os


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

def load_config(config_file):
    config_path = os.path.join(app.root_path, "config", config_file)  # Correct path
    with open(config_path, "r") as file:
        return json.load(file)  # Load JSON as a dictionary


# List of valid panels

valid_panels = load_config("panels.json")

# Connect to a serial device (comment this out if no hardware yet)
# printer = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)

@app.route("/")
def home():
    return render_template("index.html",panels=valid_panels)

@app.route("/configuration/<string:panel>")
def configure(panel):
    # panel_titles = [p["title"] for p in valid_panels]

    if panel not in valid_panels:
        abort(404)

    return render_template("config.html", panel_name=panel)


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





if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)