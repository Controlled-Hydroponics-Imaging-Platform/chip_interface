# chip_interface

Extendable and modular interface for controlled hydroponics platforms

## Features
- Serial communication 
- Kasa smart plug integrations
- Scheduling interfacess
- MQTT Backend-front end bridging

## Quick start installation
```
sudo apt install python3-venv
python3 -m venv venv

source venv/bin/activate

pip install --upgrade -r pip.txt

python app.py

```

## Structure

/CHIP_INTERFACE
│-- app.py  (Main Flask app)
│-- /templates
│    ├── layout.html  (base layout inhereted by each page)
│    ├── index.html  (main home page)
│    ├── panels.html  (configurable modular components)
│-- /static
│    ├── style.css  (CSS styling)
│    ├── script.js  (Handles WebSockets)
│-- /config
│    ├── panels.json (loaded into the home page, each configurable)
│-- /plugins (configurable systems in the future)


### Stack for interfacing with CHIP

- Flask (for the web server & API)
- Jinja2 (Flask’s templating engine for rendering HTML)
- JavaScript (jQuery, Knockout.js) (for frontend interactivity)
- WebSockets (for live printer status updates)
- Python Plugins (to extend features)
- paho-mqtt for mqtt communication

#### Libraries
flask → Runs the web server.
flask-socketio → Enables real-time updates.
Threaded(Python native), eventlet → Improves WebSocket performance.
pyserial → Handles serial communication (for talking to hardware).
Gunicorn → Handles production ready serving


### Dev information
- panels.json is your starting point, If you want to create a new panel, update json with panel information, use other panels as a template
- each panel should have an associated configuration json in config directory, associated html file in the templates folder, a pluging python script in the plugins folder which determines the back-end behaviour and plugs into the front end flask behaviour, JS file is optional but will help modularize front end-backend interactions and behavious
- you will notice the `__`init`__`.py in the plugins folder has some shared protocals that plugins can pull in from such as serial, mqtt communication etc. It also shows how plugins are loaded into loaded/reloaded into the 
- *** In future implementation I need to write how to tempalate plugin scripts..... too lazy right now

## Change log
### 0.0.3
- MQTT front-end  backend socket interface for plugins that use mqtt
- reload_plugins no longer needs to send the class interface anymore
### 0.0.2
- Implemented a modular, configurable plugin system
- Implemented a kasa_plugin for integration with kasa smart plugs
- Panels are typically congifurable front ends with plugin python scripts, html and js scripts
    - Panels are defined in the panels.json, in which you specify the, panel name, configuration file and html file which will automatically
    - the components and configurations are determined by the configuration file which is loaded /configuration/< panel_name >
- Configurations are automatically generated based on the parameter type. Compatible types include:
    - serial_port:  for configuring ports, baudrate and timeout for reading inputs from serial monitor
    - kasa_plug: for configuring the ip address, schedule and auto mode for kasa plugs
- The behaviour of these configured panels are determined by the plugin json and rendered into the panel html
### 0.0.1
- Initial structure
- Panel system that configures with sensors
- Each panel redirects to a configuration page located at /configuration/< Panel_name >
