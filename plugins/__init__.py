import os
import importlib

def load_all_plugins(app, socketio):
    plugin_dir = os.path.dirname(__file__)
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            module = importlib.import_module(f'plugins.{module_name}')
            if hasattr(module, 'plugin_blueprint'):
                app.register_blueprint(module.plugin_blueprint)
                print(f" * Registered plugin: {module_name}")
            if hasattr(module, 'start_sockets'):
                module.start_sockets(socketio, app)
                print(f" * {module_name} sockets started")