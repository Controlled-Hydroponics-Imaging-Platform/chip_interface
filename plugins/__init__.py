import os
import importlib
from datetime import datetime, time
from time import sleep
import eventlet
import threading
import serial
import paho.mqtt.client as mqtt
import json
import ssl
import random

strfmt= "%Y-%m-%d %H:%M:%S"

module_list={}


class mqttBridge:
    def __init__(self, socketio, device_name, broker_host, broker_port = 1883, topics=(), 
                 client_id=None, username=None, password=None, use_tls=False, tls_ca=None, keepalive=60, reconnect_min=1, reconnect_max=30, 
                 will_topic=None, will_payload=None, will_qos=0, will_retain=False, 
                 decode="auto"):
        self.socketio = socketio
        self.device_name = device_name
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topics = topics
        self.keepalive = keepalive
        self.decode = decode

        self._running = False
        self._client = mqtt.Client(client_id=client_id, clean_session=True)

        if username:
            try:
                self._client.username_pw_set(username=username, password=password)
            except Exception as e:
                print(f"[{self.device_name}] Error setting username/password: {e}")

        if use_tls:
            try:
                if tls_ca:
                    self._client.tls_set(ca_certs=tls_ca, certfile=None, keyfile=None,
                                         cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
                else:
                    self._client.tls_set()
                self._client.tls_insecure_set(False)
            except Exception as e:
                print(f"[{self.device_name}] TLS setup failed: {e}")
        
        if will_topic is not None:
            try:
                wp = will_payload
                if isinstance(wp, (dict, list)):
                    wp = json.dumps(wp)
                self._client.will_set(will_topic, payload=wp, qos=will_qos, retain=will_retain)
            except Exception as e:
                print(f"[{self.device_name}] Will set failed: {e}")

        try:
            self._client.reconnect_delay_set(min_delay=reconnect_min, max_delay=reconnect_max)
        except Exception as e:
            print(f"[{self.device_name}] reconnect_delay_set failed: {e}")

        # bind callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_message = self._on_message

        self.task = None
        self.last_output = {}

    # --- API ---
    def start(self):
        """ start or restart the MQTT loop in a background thread"""
        self.kill()
        self._emit_status("connecting", {"broker": f"{self.broker_host}:{self.broker_port}"})
        self._running = True

        def _connect_and_loop():
            while self._running:
                try:
                    self._client.connect(self.broker_host, self.broker_port, self.keepalive)
                    self._client.loop_start()
                    while self._running:
                        sleep(1)
                    break
                except Exception as e:
                    self._emit_status("error", {"error": str(e)})
                    print(f"[{self.device_name}] MQTT start error: {e}")
                    sleep(3)
        
        try:
            self.task = threading.Thread(target=_connect_and_loop, daemon=True)
            self.task.start()
        except Exception as e:
            print(f"[{self.device_name}] Thread start failed: {e}")

    def kill(self):
        """gracefully stop background thread and network loop"""
        self._running = False
        try:
            self._client.loop_stop()
        except Exception as e:
            print(f"[{self.device_name}] loop_stop failed: {e}")
        try:
            self._client.disconnect()
        except Exception as e:
            print(f"[{self.device_name}] disconnect failed: {e}")

        if self.task:
            try:
                self.task.join(timeout=5)
            except Exception as e:
                print(f"[{self.device_name}] Thread join failed: {e}")
            self.task = None

        self._emit_status("disconnected", {"broker": f"{self.broker_host}:{self.broker_port}"})
        print(f"[{self.device_name}] Disconnected from broker {self.broker_host}:{self.broker_port}")

    def publish(self, topic, payload, qos=0, retain=False):
        """Threadsafe publish helper."""
        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            result = self._client.publish(topic, payload=payload, qos=qos, retain=retain)
            return result.rc
        except Exception as e:
            print(f"[{self.device_name}] Publish failed: {e}")
            return -1
    
    # ---- callbacks ---
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._emit_status("connected", {"session_present": bool(flags.get("session present", 0))})
            print(f"[{self.device_name}] Connected to {self.broker_host}:{self.broker_port}")
            try:
                if isinstance(self.topics, (list, tuple)):
                    if self.topics and isinstance(self.topics[0], (list, tuple)):
                        client.subscribe(self.topics)
                    else:
                        for topic in self.topics:
                            client.subscribe(topic, 0)
                elif isinstance(self.topics, dict):
                    for t, q in self.topics.items():
                        client.subscribe((t, q))
                elif isinstance(self.topics, str):
                    client.subscribe(self.topics, 0)
            except Exception as e:
                print(f"[{self.device_name}] Subscription failed: {e}")
        else:
            self._emit_status("error", {"connect_rc": rc})
            print(f"[{self.device_name}] Connection failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        status = "disconnected" if rc == 0 else "error"
        self._emit_status(status, {"disconnect_rc": rc})
        if rc == 0:
            print(f"[{self.device_name}] Disconnected cleanly")
        else:
            print(f"[{self.device_name}] Unexpected disconnect (rc={rc})")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        self._emit_status("subscribed", {"mid": mid, "granted_qos": granted_qos})

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload
            if self.decode == "utf8" or (self.decode == "auto" and self._looks_text(payload)):
                try:
                    payload = payload.decode("utf-8")

                    payload = payload.replace("NaN", "null").replace("nan", "null") # nan is not recognized in json python 

                    if payload and payload[0] in "{[":
                        payload = json.loads(payload)
                except Exception as e:
                    print(f"[{self.device_name}] Payload decode failed: {e}")
            out = {
                "data": payload,
                "timestamp": datetime.now().strftime(strfmt),
                "topic": msg.topic
            }
            self.last_output = out
            self.socketio.emit(f"{self.device_name}_mqtt_update", out)
        except Exception as e:
            print(f"[{self.device_name}] on_message failed: {e}")

    ## --- helpers ---
    def _emit_status(self, status, extra=None):
        data = {"status": status, "device": self.device_name}
        if extra:
            data.update(extra)
        try:
            self.socketio.emit(f"{self.device_name}_status_update", data)
        except Exception as e:
            print(f"[{self.device_name}] emit_status failed: {e}")

    @staticmethod
    def _looks_text(b: bytes):
        try:
            if not b:
                return True
            high = sum(ch >= 0x80 for ch in b[:64])
            nuls = b[:64].count(0)
            return (high + nuls) <= 2
        except Exception as e:
            print(f"[looks_text] Error: {e}")
            return True

class ControlScheduler:
    def __init__(self, socketio, device_name, device_ip, schedule_config, control_callback, check_state_callback):
        self.task = None
        self.state_sync_task = None
        self.socketio = socketio
        self._running = True
        self.device_name = device_name
        self.device_ip = device_ip
        self.schedule = schedule_config  # Pass the schedule JSON list here
        self.control_callback = control_callback  # Callable to toggle plug ON/OFF
        self.check_state_callback = check_state_callback
        self.last_state = False

    def start(self):
        # self.kill()  # Always clean start
        print(f"✅ Starting control scheduler for {self.device_name}")
        self._running = True

        self.task = threading.Thread(target=self.control_schedule, daemon=True)
        self.state_sync_task = threading.Thread(target=self.sync_state_loop, daemon=True)

        self.task.start()
        self.state_sync_task.start()


    def kill(self):
        print(f"🛑 Killing control scheduler for {self.device_name}")
        self._running = False  # Signal both loops to stop

        # Kill the control task
        if self.task:
            self.task.join(timeout=5)
            print(f"✅ Control loop for {self.device_name} killed")
            self.task = None

        # Kill the sync state task
        if self.state_sync_task:
            self.state_sync_task.join(timeout=5)
            print(f"✅ Sync state loop for {self.device_name} killed")
            self.state_sync_task = None

        print(f"✅ {self.device_name} fully stopped")

    def sync_state_loop(self):
        """Periodically fetches the real plug state."""
        try:
            while self._running:
                try:
                    with eventlet.Timeout(5, False):  # ✅ Optional timeout safety
                        real_state = self.check_state_callback(self.device_ip)
                        self.last_state = real_state

                        output_data = {
                                    "data": real_state,
                                    "timestamp": datetime.now().strftime(strfmt)
                                }
                        self.socketio.emit(f"{self.device_name}_control_update", output_data)
                        # print(f"🔄 Synced state: {self.device_name} is {'ON' if real_state else 'OFF'}")
                except Exception as e:
                    print(f"⚠️ Error syncing state for {self.device_name}: {e}")
                sleep(random.uniform(0,10))
        finally:
            print(f"✅ Sync loop fully exited for {self.device_name}")

    def control_schedule(self):
        try:
            while self._running:
                try:
                    now = datetime.now()
                    today = now.strftime("%A")
                    current_time = now.time()
                    print(f"🕒 Now: {now}, Today: {today}, Current time: {current_time}")
                    print(f"📅 Schedule: {self.schedule}")
                    # print(self.schedule)

                    should_be_on = False
                    for block in self.schedule:
                        if today in block.get("days", []):
                            block_days = block.get("days",[])
                            start_time = self._parse_time(block.get("start"))
                            end_time = self._parse_time(block.get("end"))
                            print(f"🔍 Checking: {block_days}")
                            print(f"    Start: {start_time}, End: {end_time}, Now: {current_time}")
                            print(f"    Match today? {'Yes' if today in block_days else 'No'}")
                            print(f"    In range? {self._time_in_range(start_time, end_time, current_time)}")

                            if start_time and end_time and self._time_in_range(start_time, end_time, current_time):
                                should_be_on = True
                                break

                    # print(should_be_on)
                    
                    # Only act if the state needs changing
                    if should_be_on != self.last_state:
                        action = "ON" if should_be_on else "OFF"
                        print(f"🕒 [{now.strftime(strfmt)}] - {self.device_name} → {action}")
                        try:
                            self.control_callback(self.device_ip, should_be_on)
                            self.last_state = should_be_on  # ✅ Update assuming success
                        except Exception as e:
                            print(f"❌ Failed to toggle {self.device_name}: {e}")
                except Exception as loop_err:
                    print(f"❌ Unexpected crash in control loop for {self.device_name}: {loop_err}")
                    
                sleep(30)
        finally:
            print(f"✅ Schedule loop fully exited for {self.device_name}")

    def _parse_time(self, t_str):
        try:
            h, m = map(int, t_str.split(":"))
            return time(h, m)
        except (ValueError, TypeError):
            return None

    def _time_in_range(self, start, end, now_time):
        if start <= end:
            return start <= now_time <= end
        else:
            # Handles overnight schedules (start: 22:00, end: 06:00)
            return now_time >= start or now_time <= end
        
class SerialReader:
    def __init__(self, socketio, device_name, port, baudrate, timeout, process_raw_data, poll_rate):
        self.task = None
        self.device_name = device_name
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.process_raw_data = process_raw_data
        self.poll_rate = poll_rate
        self.socketio = socketio
        self.last_output = {}
        self._running = True  # ✅ Control loop for graceful shutdown

    def start(self):

        self.kill()

        print(f"🚀 Starting serial reader task for {self.device_name}")
        self._running = True
        self.task = threading.Thread(target=self.read_serial_socket, daemon=True)
        self.task.start()

    def kill(self):
        
        print(f"🛑 Killing task for {self.device_name}")
        self._running = False  # ✅ Signal loop to stop
        if self.task:
            self.task.join(timeout=5)
            self.task = None
        print(f"✅ {self.device_name} stopped")

    def read_serial_socket(self):
        try:
            while self._running:
                try:
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "connecting", "device": self.port})
                    print(f"🔌 Connecting to serial {self.device_name} ({self.port})...")
                    ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

                    ser.reset_input_buffer()
                    print(f"✅ {self.device_name} ({self.port}): Serial connection established")
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "connected", "device": self.port})

                    # Discard first few lines to sync
                    for _ in range(5):
                        try:
                            ser.readline()
                        except (serial.SerialException, OSError) as e:
                            print(f"⚠️ Sync error: {e}")
                            break  # Will trigger reconnect

                    # Main reading loop
                    while self._running:
                        try:
                            if ser.in_waiting > 0:
                                raw_data = None
                                while ser.in_waiting:
                                    raw_data = ser.readline().decode('utf-8', errors='ignore').strip()

                                if not raw_data:
                                    print(f"⚠️ Skipping bad data: {raw_data}")
                                    continue

                                processed_data = self.process_raw_data(raw_data)
                                output_data = {
                                    "data": processed_data,
                                    "timestamp": datetime.now().strftime(strfmt)
                                }
                                self.socketio.emit(f"{self.device_name}_sensor_update", output_data)
                                self.last_output = output_data

                            sleep(self.poll_rate)
                            
                        except (serial.SerialException, OSError) as e:
                            print(f"❌ Serial read error: {e}")
                            break  # Break inner loop to reconnect

                except (serial.SerialException, OSError) as e:
                    print(f"❌ Connection failed: {e}")
                    self.socketio.emit(f"{self.device_name}_status_update", {"status": "disconnected", "device": self.port})

                finally:
                    try:
                        ser.close()
                        print(f"⚠️ {self.device_name} Serial connection closed")
                    except:
                        pass

                    if self._running:
                        print("🔄 Reconnecting in 5 seconds...")
                        sleep(5)

        except eventlet.greenlet.GreenletExit:
            print(f"✅ Serial reader for {self.device_name} terminated")



def load_all_plugins(app, socketio):
    global module_list
    script_list = []
    plugin_dir = os.path.dirname(__file__)
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            module = importlib.import_module(f'plugins.{module_name}')
            module_list[module_name] = module
            if hasattr(module, 'plugin_blueprint'):
                app.register_blueprint(module.plugin_blueprint)
                print(f" * Registered plugin: {module_name}")
            if hasattr(module, 'register_serial_sockets'):
                module.register_serial_sockets(SerialReader, socketio, app)
                print(f" * {module_name} serial sockets started")
            if hasattr(module, 'register_mqtt_sockets'):
                module.register_mqtt_sockets(mqttBridge, socketio, app)
                print(f" * {module_name} mqtt sockets started")
            if hasattr(module, 'register_control_scheduler_sockets'):
                module.register_control_scheduler_sockets(ControlScheduler, socketio, app)
                print(f" * {module_name} Control Schedulers started")
            if hasattr(module, 'scripts'):
                for script in module.scripts: script_list.append(script)
                print(f" * {', '.join(script for script in module.scripts)} scripts will be loaded")

    return script_list

def reload_plugins(app, socketio):
    for module_name,module in module_list.items():
        if hasattr(module, 'reload_routine'):
            module.reload_routine(socketio, app)
            print(f"{module_name} plugins/sockets reloaded")
