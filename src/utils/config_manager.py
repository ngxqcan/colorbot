import json
import os

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        """Loads configuration from the JSON file."""
        if not os.path.exists(self.config_path):
            # Default config if file doesn't exist
            return {
                "TOGGLE_KEY": "f1",
                "TRIGGER_KEY": "f2",
                "TRIGGER_DELAY": 100,
                "FOV": 100,
                "RESOLUTION": [1920, 1080],
                "ENEMY_COLOR": "Purple"
            }
        
        try:
            with open(self.config_path, 'r') as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Error] Failed to load config: {e}")
            return {}

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
        return self.config.get(key, default)

    def set(self, key, value):
        """Sets a configuration value locally."""
        self.config[key] = value
