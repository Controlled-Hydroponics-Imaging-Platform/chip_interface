class CaptureRegistry:
    def __init__(self):
        self.providers = {}

    def register(self, name, callback):
        self.providers[name] = callback

    def collect(self):
        output = {}

        for name, callback in self.providers.items():
            try:
                output[name] = callback()
            except Exception as e:
                output[name] = {"error": str(e)}

        return output
    
capture_registry = CaptureRegistry()
