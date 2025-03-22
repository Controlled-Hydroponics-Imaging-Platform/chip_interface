from flask import Blueprint, jsonify
from flask_socketio import SocketIO
import eventlet
import serial
import os, json
import asyncio
from kasa import Discover

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