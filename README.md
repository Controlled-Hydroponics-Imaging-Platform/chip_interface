# chip_interface

## Structure
/flask_interface
│-- app.py  (Main Flask app)
│-- /templates
│    ├── index.html  (Frontend UI)
│-- /static
│    ├── style.css  (CSS styling)
│    ├── script.js  (Handles WebSockets)

#### Stack for interfacing with CHIP

- Flask (for the web server & API)
- Jinja2 (Flask’s templating engine for rendering HTML)
- JavaScript (jQuery, Knockout.js) (for frontend interactivity)
- WebSockets (for live printer status updates)
- Python Plugins (to extend features)


flask → Runs the web server.
flask-socketio → Enables real-time updates.
eventlet → Improves WebSocket performance.
pyserial → Handles serial communication (for talking to hardware).