from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO
import asyncio
from kasa import Discover, SmartPlug

plugin_blueprint = Blueprint('kasa_plug',
                             __name__,
                             url_prefix='/kasa_plug')

scripts = ["kasa_plug.js"]

# Async-safe runner to prevent RuntimeError
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    if loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        return loop.run_until_complete(coro)

# API Endpoint to get all Kasa devices
@plugin_blueprint.route("/get_kasa_devices")
def get_kasa_devices():
    devices = run_async(discover_kasa_devices())
    return jsonify(devices)

async def discover_kasa_devices():
    devices = await Discover.discover()
    device_list = []
    for addr, dev in devices.items():
        device_info = {
            "ip": addr,
            "alias": getattr(dev, 'alias', "Unknown")
        }
        device_list.append(device_info)
    return device_list


# set plug ON/OFF
@plugin_blueprint.route("/set_plug", methods=["POST"])
def set_plug():
    ip = request.args.get("ip")
    state = request.args.get("state")
    if not ip:
        return jsonify({"error": "Missing plug IP"}), 400
    
    # Convert '1'/'0', 'true'/'false', etc. to boolean
    state = str(state).lower() in ("1", "true", "on")

    result = run_async(set_kasa_plug(ip, state))
    
    return jsonify({"message": result})

async def set_kasa_plug(ip, state):
    plug = SmartPlug(ip)
    await plug.update()

    if plug.is_on == state:
        return f"✅ Plug {ip} is already {'ON' if state else 'OFF'}"
    
    if state:
        await plug.turn_on()
        return f"🔌 Plug {ip} turned ON"
    else:
        await plug.turn_off()
        return f"🔌 Plug {ip} turned OFF"



# Toggle plug ON/OFF
@plugin_blueprint.route("/toggle", methods=["POST"])
def toggle_plug():
    ip = request.args.get("ip")
    if not ip:
        return jsonify({"error": "Missing plug IP"}), 400

    result = run_async(toggle_kasa_plug(ip))
    return jsonify({"message": result})

async def toggle_kasa_plug(ip):
    plug = SmartPlug(ip)
    await plug.update()
    if plug.is_on:
        await plug.turn_off()
        return f"Plug {ip} turned OFF"
    else:
        await plug.turn_on()
        return f"Plug {ip} turned ON"

# Get the current status of the plug
@plugin_blueprint.route("/status", methods=["GET"])
def get_plug_status():
    ip = request.args.get("ip")
    if not ip:
        return jsonify({"error": "Missing plug IP"}), 400

    state = run_async(get_kasa_plug_state(ip))
    return jsonify({"ip": ip, "state": state})

async def get_kasa_plug_state(ip):
    plug = SmartPlug(ip)
    await plug.update()
    return plug.is_on