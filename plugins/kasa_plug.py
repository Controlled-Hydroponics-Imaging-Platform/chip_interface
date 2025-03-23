from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO
import eventlet
import serial
import os, json
import asyncio
from kasa import Discover, SmartPlug

plugin_blueprint = Blueprint('kasa_plug',
                __name__,
                url_prefix='/kasa_plug')

scripts =["kasa_plug.js"]


# API
@plugin_blueprint.route("/get_kasa_devices")
def get_kasa_devices():
    devices = asyncio.run(discover_kasa_devices())
    return jsonify(devices)

async def discover_kasa_devices():
    devices = await Discover.discover()
    device_list = []

    for addr, dev in devices.items():
        device_info = {
            "ip": addr,
            "alias": dev.alias if hasattr(dev, 'alias') else "Unknown"
        }
        device_list.append(device_info)

    return device_list

@plugin_blueprint.route("/toggle", methods=["POST"])
def toggle_plug():
    ip = request.args.get("ip")
    if not ip:
        return jsonify({"error": "Missing plug IP"}), 400

    result = asyncio.run(toggle_kasa_plug(ip))
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
    
@plugin_blueprint.route("/status", methods=["GET"])
def get_plug_status():
    ip = request.args.get("ip")
    if not ip:
        return jsonify({"error": "Missing plug IP"}), 400

    state = asyncio.run(get_kasa_plug_state(ip))
    return jsonify({"ip": ip, "state": state})  # state: True for ON, False for OFF

async def get_kasa_plug_state(ip):
    plug = SmartPlug(ip)
    await plug.update()
    return plug.is_on