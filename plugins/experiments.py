from flask import Blueprint, jsonify, request, url_for, send_file, current_app
import os, json
from pathlib import Path
from datetime import datetime
from time import sleep
strfmt= "%Y-%m-%d %H:%M:%S"
from lib.pi_data_storage_handler import database_handler as dh
from influxdb_client_3 import InfluxDBClient3, Point
import io
import zipfile


data_handler = None
last_seen_data = {}
panel_association = "Experiments"
root_path = None
active_experiment = None
image_root_path = None
active_image_path = None

plugin_blueprint = Blueprint('experiments',
                __name__,
                url_prefix='/experiments')

scripts =[]

def load_config(root_path, config_file):
        config_path = os.path.join(root_path, "config", config_file)  # Correct path
        try:
            with open(config_path, "r") as file:
                return json.load(file)  # Load JSON as a dictionary
        except json.JSONDecodeError as e:
            print(f"🚨 JSON Error: {e}")
            return {}

def load_routine(app):
    global data_handler, active_experiment, image_root_path, active_image_path

    config_file = load_config(app.root_path, "panels.json")[panel_association]['config']['set_to']
    config = load_config(app.root_path, config_file)

    active_experiment = config["active_experiment"]["set_to"]
    image_root_path = config["image_storage_path"]["set_to"]
    active_image_path = image_root_path + "/" + active_experiment

    data_handler = dh.SQLiteDataHandler(config["database_path"]["set_to"],dh.DEFAULT_TABLES)


def reload_routine(socketio, app):
    global data_handler, active_experiment

    # Kill datahandlers
    data_handler.kill_all()
    data_handler = None
    active_experiment = None

    # Re-register
    load_routine(app)

### API

@plugin_blueprint.route("/get_all_experiments")
def get_all_experiments():
    global data_handler

    with data_handler.connect_db() as conn:
        rows = conn.execute("""
        SELECT *
        FROM experiments
        ORDER BY start_time DESC
        """).fetchall()

    experiments = [dict(row) for row in rows]

    return jsonify({
        "ok": True,
        "experiments": experiments
    })

@plugin_blueprint.route("/create_new_experiment", methods=["POST"])
def create_new_experiment():
    global data_handler
    data = request.get_json() or request.form

    if not data.get("experiment_id"):
        return jsonify({
            "ok": False,
            "error": "Experiment id is required"
        }), 400

    table_content = {key : value for key, value in data.items() }

    data_handler.insert("experiments",table_content)

    return jsonify({
        "ok": True,
        "experiment_id": table_content["experiment_id"]
    })


@plugin_blueprint.route("/set_active_experiment", methods=["POST"])
def set_active_experiment():
    global active_experiment, data_handler

    data = request.get_json() or request.form
    experiment_id = data.get("experiment_id")

    if not experiment_id:
        return jsonify({
            "ok": False,
            "error": "experiment_id is required"
        }), 400

    # Check experiment exists
    with data_handler.connect_db() as conn:
        row = conn.execute("""
            SELECT *
            FROM experiments
            WHERE experiment_id = ?
        """, (experiment_id,)).fetchone()

    if row is None:
        return jsonify({
            "ok": False,
            "error": "Experiment does not exist"
        }), 404

    # Update runtime variable
    active_experiment = experiment_id

    # Update config file so it survives restart
    config_file = load_config(current_app.root_path, "panels.json")[panel_association]["config"]["set_to"]
    config_path = os.path.join(current_app.root_path, "config", config_file)

    with open(config_path, "r") as f:
        config = json.load(f)

    config["active_experiment"]["set_to"] = experiment_id

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

    current_app.reload_all_plugins()

    return jsonify({
        "ok": True,
        "active_experiment": active_experiment
    })

@plugin_blueprint.route("/get_active_experiment")
def get_active_experiment():
    global active_experiment

    if active_experiment is None:
        return jsonify({
            "ok": True,
            "active_experiment": None,
            "experiment": None
        })

    with data_handler.connect_db() as conn:
        row = conn.execute("""
            SELECT *
            FROM experiments
            WHERE experiment_id = ?
        """, (active_experiment,)).fetchone()

    return jsonify({
        "ok": True,
        "active_experiment": active_experiment,
        "experiment": None if row is None else dict(row)
    })

@plugin_blueprint.route("/download_database", methods=["GET"])
def download_database():
    global data_handler

    database_path = data_handler.db_path

    if not database_path.exists():
        return jsonify({
            "ok": False,
            "error": "Database does not exist"
        }), 404
    
    return send_file(database_path,
                     as_attachment=True,
                     download_name=database_path.name,
                     mimetype="application/vnd.sqlite3")

@plugin_blueprint.route("/download_image_dataset")
@plugin_blueprint.route("/download_image_dataset/<experiment_id>", methods=["GET"])
def download_images(experiment_id=None):
    global image_root_path, active_image_path, active_experiment

    if experiment_id is None:
        image_path = Path(image_root_path)
        file_name = "CHIP_IMAGE_DATASET"
    elif experiment_id == "active":
        image_path = Path(active_image_path)
        file_name = active_experiment
    else:
        exp_path = image_root_path + "/" + experiment_id
        image_path = Path(exp_path)
        file_name = experiment_id


    if not image_path.exists():
        return jsonify({
            "ok": False,
            "error": "Image directory does not exist"
        }), 404
    
    # image_files = [
    #     p for p in image_path.iterdir()
    #     if p.is_file() and p.suffix.lower() in {
    #         ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"
    #     }
    # ]

    image_files = [
    p for p in image_path.rglob("*")
    if p.is_file() and p.suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"
    }
]

    if not image_files:
        return jsonify({
            "ok": False,
            "error": "No images found."
        }), 404
    
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in image_files:
            # zf.write(image, arcname=image.name)
            zf.write(image, arcname=image.relative_to(image_path))

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"{file_name}.zip",
        mimetype="application/zip"
    )

# @plugin_blueprint.route("/processed_data")
# def get_mqtt_data():
#     global root_path
#     root_path=current_app.root_path
#     return jsonify(root_path)