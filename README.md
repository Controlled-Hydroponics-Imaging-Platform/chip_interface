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
### 0.0.1
- Initial structure
- Panel system that configures with sensors
- Each panel redirects to a configuration page located at /configuration/< Panel_name >
