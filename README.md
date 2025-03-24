# chip_interface

Extendable and modular interface for controlled hydroponics platforms

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

#### Libraries
flask → Runs the web server.
flask-socketio → Enables real-time updates.
eventlet → Improves WebSocket performance.
pyserial → Handles serial communication (for talking to hardware).

## Change log
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
