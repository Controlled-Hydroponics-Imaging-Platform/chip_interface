import os
import importlib

def load_all_plugins(app, socketio):
    script_list = []
    plugin_dir = os.path.dirname(__file__)
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            module = importlib.import_module(f'plugins.{module_name}')
            if hasattr(module, 'plugin_blueprint'):
                app.register_blueprint(module.plugin_blueprint)
                print(f" * Registered plugin: {module_name}")
            if hasattr(module, 'register_sockets'):
                module.register_sockets(socketio, app)
                print(f" * {module_name} sockets started")
            if hasattr(module, 'scripts'):
                for script in module.scripts: script_list.append(script)
                print(f" * {', '.join(script for script in module.scripts)} scripts will be loaded")

    return script_list