import sys
import threading
import time
import cv2
import numpy as np
from drivers.screen import ScreenCapture
from drivers.mouse import PicoMouse

class Colorbot:
    """
    Optimized Color Detection & Target Tracking engine for 1-PC (and 2-PC).
    """
    # Tuned HSV ranges for Valorant enemy outlines
    COLOR_RANGES = {
        "Purple": {
            "lower": np.array([140, 105, 120]),
            "upper": np.array([160, 255, 255])
        },
        "Yellow": {
            "lower": np.array([25, 110, 120]),
            "upper": np.array([35, 255, 255])
        },
        "Red": {
            "lower1": np.array([0, 140, 120]),
            "upper1": np.array([10, 255, 255]),
            "lower2": np.array([170, 140, 120]),
            "upper2": np.array([180, 255, 255])
        }
    }

    def __init__(self, x, y, grabzone, color_name="Purple", aim_enabled=False, trigger_enabled=False,
                 sensitivity=0.35, smoothing=0.3, head_offset=8, trigger_delay=25,
                 capture_method="auto", mouse_method="auto"):
        self.x = int(x)
        self.y = int(y)
        self.grabzone = int(grabzone)
        self.color_name = color_name
        self.aim_enabled = aim_enabled
        self.trigger_enabled = trigger_enabled
        self.sensitivity = max(0.01, float(sensitivity))
        self.smoothing = max(0.01, min(1.0, float(smoothing)))
        self.head_offset = int(head_offset)
        self.trigger_delay = max(0, int(trigger_delay)) / 1000.0  # convert ms to sec
        
        self.last_trigger_time = 0.0

        # Enable high-resolution Windows timer if on Windows
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                pass

        self.mouse = PicoMouse(method=mouse_method)
        self.grabber = ScreenCapture(self.x, self.y, self.grabzone, method=capture_method)
        
        self.running = False
        self.thread = None

    def _get_color_mask(self, hsv):
        """Generates a binary mask based on the selected enemy outline color."""
        if self.color_name == "Red":
            ranges = self.COLOR_RANGES["Red"]
            mask1 = cv2.inRange(hsv, ranges["lower1"], ranges["upper1"])
            mask2 = cv2.inRange(hsv, ranges["lower2"], ranges["upper2"])
            return cv2.bitwise_or(mask1, mask2)
        else:
            ranges = self.COLOR_RANGES.get(self.color_name, self.COLOR_RANGES["Purple"])
            return cv2.inRange(hsv, ranges["lower"], ranges["upper"])

    def start(self):
        """Starts the detection and aim loop thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        """Stops the loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def _run(self):
        """Main processing loop running at maximum possible frequency."""
        while self.running:
            if not self.aim_enabled and not self.trigger_enabled:
                time.sleep(0.005)
                continue

            self.process()
            time.sleep(0.0005)

    def process(self):
        screen = self.grabber.get_screen()
        if screen is None or screen.size == 0:
            return

        # Screen is already ROI (grabzone x grabzone)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = self._get_color_mask(hsv)

        # Morphological dilation to bridge fragmented outline pixels
        dilated = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return

        # Find largest contour in ROI (assumed closest target)
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 10:
            return

        x, y, w, h = cv2.boundingRect(contour)
        
        # Center coordinates of the bounding box
        cX = x + w // 2
        cY = y + h // 2
        
        gz_center = self.grabzone // 2

        # 1. Aimbot Logic
        if self.aim_enabled:
            # Target head / upper contour: y + head_offset (or topmost pixel)
            target_y = y + min(self.head_offset, h // 2)
            
            x_diff = cX - gz_center
            y_diff = target_y - gz_center

            # Valorant sensitivity to pixel displacement formula:
            # 1.07437623 * (Sensitivity ^ -0.9936827126)
            sens_scale = 1.07437623 * (self.sensitivity ** -0.9936827126)
            
            move_x = x_diff * sens_scale * self.smoothing
            move_y = y_diff * sens_scale * self.smoothing
            
            # Deadzone check to avoid jitter
            if abs(move_x) >= 0.5 or abs(move_y) >= 0.5:
                self.mouse.move(move_x, move_y)

        # 2. Triggerbot Logic
        if self.trigger_enabled:
            # Check if crosshair center (gz_center, gz_center) falls within target bounding box
            if abs(cX - gz_center) <= max(3, w // 2) and abs(cY - gz_center) <= max(6, h // 2):
                now = time.time()
                if now - self.last_trigger_time >= (self.trigger_delay + 0.15):
                    if self.trigger_delay > 0:
                        time.sleep(self.trigger_delay)
                    self.mouse.click("left")
                    self.last_trigger_time = time.time()

    def close(self):
        """Clean up resources."""
        self.stop()
        if hasattr(self, 'mouse') and self.mouse:
            self.mouse.close()
        if hasattr(self, 'grabber') and self.grabber:
            self.grabber.stop()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass

    def __del__(self):
        self.close()
