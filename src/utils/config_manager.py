import json
import os

DEFAULT_CONFIG = {
    "MASTER_TOGGLE_KEY": "f1",
    "AIM_KEY": "RMB",
    "AIM_MODE": "Hold",
    "AIM_TARGET": "Head",
    "AIM_ENABLED": False,
    "MAGNET_ENABLED": False,
    "MAGNET_KEY": "RMB",
    "MAGNET_MODE": "Tap",
    "BURST_COUNT": 2,
    "BURST_DELAY": 80,
    "BURST_COOLDOWN": 250,
    "TAP_COOLDOWN": 180,
    "MAGNET_TARGET": "Head",
    "MAGNET_FOV": 45,
    "MAGNET_SMOOTHING": 0.20,
    "TRIGGER_KEY": "f2",
    "TRIGGER_MODE": "Toggle",
    "TRIGGER_ENABLED": False,
    "TRIGGER_DELAY": 30,
    "FOV": 45,
    "RESOLUTION": ["1920", "1080"],
    "ENEMY_COLOR": "Purple",
    "SENSITIVITY": 0.35,
    "SMOOTHING": 0.18,
    "HEAD_OFFSET": 7,
    "ANTI_SHAKE_ENABLED": True,
    "DEADZONE": 1.0,
    "RCS_ENABLED": True,
    "RCS_PITCH": 2.5,
    "RCS_YAW": 0.0,
    "RCS_START_DELAY_MS": 100,
    "KMNET_IP": "192.168.2.188",
    "KMNET_PORT": 16896,
    "KMNET_UUID": "46405c53",
    "CAPTURE_METHOD": "Auto",
    "MOUSE_METHOD": "Auto",
    "PREVIEW_MODE": "Camera + HUD",
    "PREVIEW_SIZE": "500x500"
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
                if "TOGGLE_KEY" in data and "AIM_KEY" not in data:
                    data["AIM_KEY"] = data["TOGGLE_KEY"]
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
