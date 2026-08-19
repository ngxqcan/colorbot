import sys
import threading
import time
import cv2
import numpy as np
from drivers.screen import ScreenCapture
from drivers.mouse import PicoMouse

class Colorbot:
    """
    High-Speed Color Detection, Target Tracking & Preview Engine for Valorant.
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
                 aim_mode="Hold", trigger_mode="Toggle",
                 sensitivity=0.35, smoothing=0.3, head_offset=8, trigger_delay=25,
                 capture_method="auto", mouse_method="auto"):
        self.x = int(x)
        self.y = int(y)
        self.grabzone = max(10, (int(grabzone) // 2) * 2)
        self.color_name = color_name
        
        # Master switches
        self.aim_enabled = bool(aim_enabled)
        self.trigger_enabled = bool(trigger_enabled)
        
        # Modes ('Hold', 'Toggle', 'Always')
        self.aim_mode = aim_mode
        self.trigger_mode = trigger_mode
        
        # Dynamic live key states
        self.is_aim_key_pressed = False
        self.is_trigger_key_pressed = False
        self.aim_toggled = False
        self.trigger_toggled = False

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
        self.lock = threading.Lock()

        # Telemetry & Preview Data
        self.last_frame = None
        self.last_mask = None
        self.last_target = {"found": False}
        self.is_aiming_now = False
        self.is_triggering_now = False
        self.loop_fps = 0.0
        self.latency_ms = 0.0
        self._fps_count = 0
        self._fps_time = time.time()

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
        """Starts the continuous detection and aim loop."""
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
        """Main processing loop running at maximum frequency."""
        while self.running:
            self.process()
            time.sleep(0.0005)

    def process(self):
        t_start = time.perf_counter()
        
        screen = self.grabber.get_screen()
        if screen is None or screen.size == 0:
            return

        # Screen is ROI (grabzone x grabzone)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = self._get_color_mask(hsv)

        # Morphological dilation to bridge fragmented outline pixels
        dilated = cv2.dilate(mask, None, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        gz_center = self.grabzone // 2
        target_info = {"found": False}
        aiming_this_tick = False
        triggering_this_tick = False

        if contours:
            # Filter contours by minimum area (avoid single-pixel noise)
            valid_contours = [c for c in contours if cv2.contourArea(c) >= 8]
            
            if valid_contours:
                # Find closest contour to center crosshair
                def dist_to_center(c):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    cx_c = bx + bw // 2
                    cy_c = by + bh // 2
                    return (cx_c - gz_center) ** 2 + (cy_c - gz_center) ** 2

                best_contour = min(valid_contours, key=dist_to_center)
                x, y, w, h = cv2.boundingRect(best_contour)
                
                cX = x + w // 2
                cY = y + h // 2
                
                # Head target location: top of contour + head_offset
                target_y = y + min(self.head_offset, max(1, h // 3))
                
                x_diff = cX - gz_center
                y_diff = target_y - gz_center
                dist = np.hypot(x_diff, y_diff)

                target_info = {
                    "found": True,
                    "x": x, "y": y, "w": w, "h": h,
                    "cX": cX, "cY": cY,
                    "target_y": target_y,
                    "x_diff": x_diff, "y_diff": y_diff,
                    "dist": round(dist, 1)
                }

                # 1. Aimbot Logic
                should_aim = False
                if self.aim_enabled:
                    if self.aim_mode == "Hold":
                        should_aim = self.is_aim_key_pressed
                    elif self.aim_mode == "Toggle":
                        should_aim = self.aim_toggled
                    elif self.aim_mode == "Always":
                        should_aim = True

                if should_aim:
                    # Valorant sensitivity to pixel displacement scaling formula:
                    # 1.07437623 * (Sensitivity ^ -0.9936827126)
                    sens_scale = 1.07437623 * (self.sensitivity ** -0.9936827126)
                    
                    move_x = x_diff * sens_scale * self.smoothing
                    move_y = y_diff * sens_scale * self.smoothing
                    
                    # Deadzone threshold
                    if abs(move_x) >= 0.4 or abs(move_y) >= 0.4:
                        self.mouse.move(move_x, move_y)
                        aiming_this_tick = True

                # 2. Triggerbot Logic
                should_trigger = False
                if self.trigger_enabled:
                    if self.trigger_mode == "Hold":
                        should_trigger = self.is_trigger_key_pressed
                    elif self.trigger_mode == "Toggle":
                        should_trigger = self.trigger_toggled
                    elif self.trigger_mode == "Always":
                        should_trigger = True

                if should_trigger:
                    # Check if crosshair center (gz_center, gz_center) falls within target bounding box
                    if abs(cX - gz_center) <= max(3, w // 2) and abs(cY - gz_center) <= max(6, h // 2):
                        now = time.time()
                        if now - self.last_trigger_time >= (self.trigger_delay + 0.15):
                            if self.trigger_delay > 0:
                                time.sleep(self.trigger_delay)
                            self.mouse.click("left")
                            self.last_trigger_time = time.time()
                            triggering_this_tick = True

        # Measure end-to-end processing latency for this cycle
        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        
        # Store preview and telemetry state thread-safely
        with self.lock:
            self.last_frame = screen
            self.last_mask = dilated
            self.last_target = target_info
            self.is_aiming_now = aiming_this_tick
            self.is_triggering_now = triggering_this_tick
            # Exponential smoothed latency
            self.latency_ms = 0.85 * self.latency_ms + 0.15 * t_elapsed_ms if self.latency_ms > 0 else t_elapsed_ms

        self._update_fps()

    def _update_fps(self):
        self._fps_count += 1
        now = time.time()
        elapsed = now - self._fps_time
        if elapsed >= 1.0:
            self.loop_fps = self._fps_count / elapsed
            self._fps_count = 0
            self._fps_time = now

    def get_preview_data(self):
        """
        Thread-safe getter for the UI Live Preview canvas.
        Returns: (frame, mask, target_info, fps, latency_ms, is_aiming_now, is_triggering_now)
        """
        with self.lock:
            frame = self.last_frame.copy() if self.last_frame is not None else None
            mask = self.last_mask.copy() if self.last_mask is not None else None
            target = self.last_target.copy()
            fps = self.loop_fps
            latency = self.latency_ms
            is_aiming = self.is_aiming_now
            is_triggering = self.is_triggering_now
            
        return frame, mask, target, fps, latency, is_aiming, is_triggering

    def update_roi(self, cx, cy, grabzone):
        """Updates the ROI center and grabzone size."""
        self.grabzone = max(10, (int(grabzone) // 2) * 2)
        self.x = int(cx) - self.grabzone // 2
        self.y = int(cy) - self.grabzone // 2
        self.grabber.update_roi(self.x, self.y, self.grabzone)

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
