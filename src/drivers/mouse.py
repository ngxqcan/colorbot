from makcu import create_controller, MouseButton
import sys

class PicoMouse:
    def __init__(self):
        try:
            self.controller = create_controller(debug=False, auto_reconnect=True)
            if not self.controller.is_connected():
                self.controller.connect()
        except Exception as e:
            print(f"[Error] Failed to connect to Makcu device: {e}")
            sys.exit(1)

    def move(self, x, y):
        """Moves the mouse relatively by x and y."""
        try:
            self.controller.move(int(x), int(y))
        except Exception as e:
            print(f"[Error] Mouse move failed: {e}")

    def click(self, button=MouseButton.LEFT):
        """Clicks the specified mouse button."""
        try:
            self.controller.click(button)
        except Exception as e:
            print(f"[Error] Mouse click failed: {e}")

    def close(self):
        """Disconnects the controller."""
        if hasattr(self, 'controller') and self.controller:
            self.controller.disconnect()
        
    def __del__(self):
        self.close()
