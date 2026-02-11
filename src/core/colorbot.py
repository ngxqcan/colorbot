import threading
import time
import cv2
import numpy as np
from drivers.screen import ScreenCapture
from drivers.mouse import PicoMouse

class Colorbot:
    # Color ranges for different enemy highlights
    COLOR_RANGES = {
        "Purple": {
            "lower": np.array([140, 110, 150]),
            "upper": np.array([150, 195, 255])
        },
        "Red": {
            "lower": np.array([0, 150, 150]), # Fixed: Red range was duplicate of Purple
            "upper": np.array([10, 255, 255])
        },
        "Yellow": {
            "lower": np.array([30, 125, 150]),
            "upper": np.array([30, 255, 255])
        }
    }

    def __init__(self, x, y, grabzone, color_name, aim_enabled, trigger_enabled):
        self.range = self.COLOR_RANGES.get(color_name, self.COLOR_RANGES["Purple"])
        self.aim_enabled = aim_enabled
        self.trigger_enabled = trigger_enabled
        
        self.mouse = PicoMouse()  
        self.grabber = ScreenCapture(x, y, grabzone)  
        self.running = False
        self.thread = None

    def start(self):
        """Starts the detection thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        """Stops the detection thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        while self.running:
            if self.aim_enabled: 
                self.process("move") 
            if self.trigger_enabled: 
                self.process("click")
            time.sleep(0.001) # Small sleep to prevent CPU hogging

    def process(self, action):
        screen = self.grabber.get_screen()  
        if screen is None:
            return

        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)  
        mask = cv2.inRange(hsv, self.range["lower"], self.range["upper"]) 
        dilated = cv2.dilate(mask, None, iterations=5)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            return

        # Find the largest contour (assumed to be the enemy)
        contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(contour)  
        
        # Center of the contour
        cX = x + w // 2
        cY = y + h // 2 
        
        # Grabzone center
        gz_center = self.grabber.grabzone // 2

        if action == "move":
            # Aim at the head (upper part of the contour)
            target_y = y + 9 # Offset for head
            x_diff = cX - gz_center
            y_diff = target_y - gz_center
            self.mouse.move(x_diff * 0.2, y_diff * 0.2)

        elif action == "click":
            # Trigger if center is within a small box around the grabzone center
            if abs(cX - gz_center) <= 4 and abs(cY - gz_center) <= 10:
                self.mouse.click()

    def close(self):
        """Clean up resources."""
        self.stop()
        if hasattr(self, 'mouse'):
            self.mouse.close()
        if hasattr(self, 'grabber'):
            self.grabber.stop()

    def __del__(self):
        self.close()
