import json
import os

DEFAULT_CONFIG = {
    "TOGGLE_KEY": "f1",
    "AIM_MODE": "Hold",
    "TRIGGER_KEY": "f2",
    "TRIGGER_DELAY": 25,
    "FOV": 60,
    "RESOLUTION": ["1920", "1080"],
    "ENEMY_COLOR": "Purple",
    "SENSITIVITY": 0.35,
    "SMOOTHING": 0.3,
    "HEAD_OFFSET": 8,
    "CAPTURE_METHOD": "Auto",
    "MOUSE_METHOD": "Auto"
}

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        """Loads configuration from the JSON file with default fallbacks."""
        if not os.path.exists(self.config_path):
            self.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r') as file:
                data = json.load(file)
                # Merge missing keys from DEFAULT_CONFIG
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Error] Failed to load config: {e}. Using defaults.")
            return DEFAULT_CONFIG.copy()

    def save_config(self, config_data):
        """Saves configuration data to the JSON file."""
        self.config = config_data
        try:
            with open(self.config_path, 'w') as file:
                json.dump(config_data, file, indent=4)
            return True
        except IOError as e:
            print(f"[Error] Failed to save config: {e}")
            return False

    def get(self, key, default=None):
        """Gets a configuration value."""
        if default is None:
            default = DEFAULT_CONFIG.get(key)
        return self.config.get(key, default)

    def set(self, key, value):
        """Sets a configuration value locally."""
        self.config[key] = value
