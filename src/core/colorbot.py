import sys
import threading
import time
import cv2
import numpy as np
from drivers.screen import ScreenCapture
from drivers.mouse import PicoMouse

class Colorbot:
    """
    High-Precision Color Detection, Target Tracking & Magnet Engine for Valorant.
    Includes Silhouette Merging, Center-of-Head targeting, and Anti-Jitter dampening.
    """
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
                 aim_mode="Hold", trigger_mode="Toggle", aim_target="Head",
                 magnet_mode="Tap", burst_count=2, burst_delay=80,
                 sensitivity=0.35, smoothing=0.18, head_offset=7, trigger_delay=25,
                 capture_method="auto", mouse_method="auto"):
        self.x = int(x)
        self.y = int(y)
        self.grabzone = max(10, (int(grabzone) // 2) * 2)
        self.color_name = color_name
        
        # Master switches
        self.aim_enabled = bool(aim_enabled)
        self.trigger_enabled = bool(trigger_enabled)
        
        # Modes ('Hold', 'Magnet', 'Toggle', 'Always')
        self.aim_mode = aim_mode
        self.trigger_mode = trigger_mode
        
        # Target Bone ('Head', 'Neck', 'Body', 'Auto')
        self.aim_target = aim_target
        
        # Magnet Firing Mode ('Tap', 'Burst (2-Shot)', 'Burst (3-Shot)', 'Continuous')
        self.magnet_mode = magnet_mode
        self.burst_count = max(1, int(burst_count))
        self.burst_delay = max(10, int(burst_delay)) / 1000.0  # seconds

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

        # Sub-pixel accumulator to eliminate float-rounding jitter
        self.acc_x = 0.0
        self.acc_y = 0.0
        self.last_processed_frame_id = -1
        self.last_filtered_target = None

        # Morphological structuring elements for bridging outline gaps
        self.close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 9))

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
        """Main processing loop running smoothly without overshooting."""
        while self.running:
            self.process()
            time.sleep(0.001)

    def _find_unified_targets(self, mask, gz_center):
        """
        Connects fragmented enemy outline pixels into full unified character bounding boxes.
        Finds true horizontal and vertical centers instead of outline edges.
        """
        # 1. Close gaps between left & right glowing outlines
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.close_kernel)
        dilated = cv2.dilate(closed, None, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, dilated

        # Filter out tiny noise dots
        boxes = []
        for c in contours:
            if cv2.contourArea(c) >= 12:
                bx, by, bw, bh = cv2.boundingRect(c)
                # Ignore aspect ratios that can't be enemy players
                if bh >= 4 and bw >= 3:
                    boxes.append([bx, by, bx + bw, by + bh])

        if not boxes:
            return None, dilated

        # 2. Cluster/merge overlapping boxes of the same enemy silhouette
        merged_boxes = []
        for box in sorted(boxes, key=lambda b: (b[0], b[1])):
            x1, y1, x2, y2 = box
            merged = False
            for m in merged_boxes:
                # If boxes overlap or are within close proximity (same player body parts)
                if not (x2 + 8 < m[0] or x1 - 8 > m[2] or y2 + 8 < m[1] or y1 - 8 > m[3]):
                    m[0] = min(m[0], x1)
                    m[1] = min(m[1], y1)
                    m[2] = max(m[2], x2)
                    m[3] = max(m[3], y2)
                    merged = True
                    break
            if not merged:
                merged_boxes.append([x1, y1, x2, y2])

        # 3. Pick the closest unified character silhouette to crosshair
        def box_dist(b):
            cx = (b[0] + b[2]) // 2
            cy = (b[1] + b[3]) // 2
            return (cx - gz_center) ** 2 + (cy - gz_center) ** 2

        best = min(merged_boxes, key=box_dist)
        x = best[0]
        y = best[1]
        w = max(4, best[2] - best[0])
        h = max(6, best[3] - best[1])

        return (x, y, w, h), dilated

    def _calculate_target_point(self, x, y, w, h, gz_center):
        """
        Calculates the TRUE center of the head/neck/body inside the character model,
        not on the colored outline stroke.
        """
        # True horizontal center of the character's body/head
        raw_cX = x + w // 2
        
        target_mode = self.aim_target.lower() if self.aim_target else "head"
        
        if "body" in target_mode or "chest" in target_mode:
            raw_target_y = y + int(h * 0.48)
        elif "neck" in target_mode:
            raw_target_y = y + int(h * 0.25)
        elif "auto" in target_mode:
            head_y = y + min(self.head_offset, max(3, int(h * 0.14)))
            neck_y = y + int(h * 0.25)
            body_y = y + int(h * 0.48)
            bones = [head_y, neck_y, body_y]
            raw_target_y = min(bones, key=lambda by: abs(by - gz_center))
        else: # "head" default - target eyes/nose center inside skull
            # Head height is roughly top 15%-20% of character silhouette
            head_offset_clamped = min(self.head_offset, max(3, int(h * 0.18)))
            raw_target_y = y + head_offset_clamped

        # Target coordinate stabilization filter (prevents detection micro-jitter)
        if self.last_filtered_target is not None:
            prev_x, prev_y = self.last_filtered_target
            delta_dist = np.hypot(raw_cX - prev_x, raw_target_y - prev_y)
            if delta_dist < 2.5:
                cX = int(0.70 * prev_x + 0.30 * raw_cX)
                target_y = int(0.70 * prev_y + 0.30 * raw_target_y)
            elif delta_dist < 6.0:
                cX = int(0.40 * prev_x + 0.60 * raw_cX)
                target_y = int(0.40 * prev_y + 0.60 * raw_target_y)
            else:
                cX = raw_cX
                target_y = raw_target_y
        else:
            cX = raw_cX
            target_y = raw_target_y

        self.last_filtered_target = (cX, target_y)
        return cX, target_y

    def _execute_magnet_fire(self):
        """Handles Tap vs Burst vs Continuous firing logic in Magnet mode."""
        mode_str = self.magnet_mode.lower() if self.magnet_mode else "tap"
        
        if "burst" in mode_str:
            shots = 3 if "3" in mode_str else (2 if "2" in mode_str else self.burst_count)
            for _ in range(shots):
                self.mouse.click("left", delay=0.015)
                time.sleep(self.burst_delay)
            time.sleep(0.06)
        elif "continuous" in mode_str or "spray" in mode_str:
            self.mouse.click("left", delay=0.02)
        else: # "tap" mode
            self.mouse.click("left", delay=0.015)

    def process(self):
        t_start = time.perf_counter()
        
        screen, frame_id = self.grabber.get_screen_with_id()
        if screen is None or screen.size == 0:
            return

        is_new_frame = (frame_id != self.last_processed_frame_id)
        self.last_processed_frame_id = frame_id

        # Screen is ROI (grabzone x grabzone)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = self._get_color_mask(hsv)

        gz_center = self.grabzone // 2
        target_info = {"found": False}
        aiming_this_tick = False
        triggering_this_tick = False

        # Unified character detection & Silhouette bridging
        box_data, dilated_mask = self._find_unified_targets(mask, gz_center)

        if box_data is not None:
            x, y, w, h = box_data
            cX, target_y = self._calculate_target_point(x, y, w, h, gz_center)
            
            x_diff = cX - gz_center
            y_diff = target_y - gz_center
            dist = np.hypot(x_diff, y_diff)

            target_info = {
                "found": True,
                "x": x, "y": y, "w": w, "h": h,
                "cX": cX, "cY": y + h // 2,
                "target_y": target_y,
                "x_diff": x_diff, "y_diff": y_diff,
                "dist": round(dist, 1),
                "bone": self.aim_target
            }

            # Determine active states based on Aim Mode
            is_magnet_mode = (self.aim_mode == "Magnet")
            
            should_aim = False
            if self.aim_enabled:
                if self.aim_mode == "Hold" or is_magnet_mode:
                    should_aim = self.is_aim_key_pressed
                elif self.aim_mode == "Toggle":
                    should_aim = self.aim_toggled
                elif self.aim_mode == "Always":
                    should_aim = True

            should_trigger = False
            if self.trigger_enabled:
                if self.trigger_mode == "Hold":
                    should_trigger = self.is_trigger_key_pressed
                elif self.trigger_mode == "Toggle":
                    should_trigger = self.trigger_toggled
                elif self.trigger_mode == "Always":
                    should_trigger = True

            # In Magnet mode, trigger activates whenever aim key is held and target is in crosshair
            if is_magnet_mode and self.aim_enabled and self.is_aim_key_pressed:
                should_trigger = True

            # 1. Aimbot Logic (Anti-Jitter Smooth Humanized Movement)
            if should_aim and is_new_frame:
                # Deadzone threshold: within 1.2px, do NOT move (prevents 1px micro-vibration)
                if dist >= 1.2:
                    # Valorant sensitivity to pixel displacement scaling formula:
                    # 1.07437623 * (Sensitivity ^ -0.9936827126)
                    sens_scale = 1.07437623 * (self.sensitivity ** -0.9936827126)
                    
                    target_move_x = x_diff * sens_scale
                    target_move_y = y_diff * sens_scale
                    
                    # Apply smooth factor
                    smooth_factor = max(0.02, min(1.0, self.smoothing))
                    
                    # Ease-in deceleration curve when near crosshair
                    if dist < 5.0:
                        ease = min(1.0, (dist / 5.0) ** 1.3)
                        smooth_factor *= ease

                    step_x = target_move_x * smooth_factor
                    step_y = target_move_y * smooth_factor

                    # Velocity Limiter (Clamps maximum movement per frame to prevent snappy jerks)
                    max_step = max(2.5, dist * 0.40 * (self.smoothing + 0.4))
                    step_dist = np.hypot(step_x, step_y)
                    if step_dist > max_step:
                        scale = max_step / step_dist
                        step_x *= scale
                        step_y *= scale

                    # Sub-pixel delta accumulator
                    self.acc_x += step_x
                    self.acc_y += step_y
                    
                    dx = int(round(self.acc_x))
                    dy = int(round(self.acc_y))
                    
                    if dx != 0 or dy != 0:
                        self.acc_x -= dx
                        self.acc_y -= dy
                        self.mouse.move(dx, dy)
                        aiming_this_tick = True

            # 2. Triggerbot / Magnet Auto-Fire Logic
            if should_trigger:
                # Hitbox check centered on head/chest
                hitbox_w = max(4, w // 2)
                hitbox_h = max(5, int(h * 0.35))
                if abs(cX - gz_center) <= hitbox_w and abs(target_y - gz_center) <= hitbox_h:
                    now = time.time()
                    if is_magnet_mode:
                        mode_str = self.magnet_mode.lower() if self.magnet_mode else "tap"
                        cooldown = 0.26 if "burst" in mode_str else 0.18
                    else:
                        cooldown = 0.12
                        
                    if now - self.last_trigger_time >= (self.trigger_delay + cooldown):
                        if self.trigger_delay > 0:
                            time.sleep(self.trigger_delay)
                        
                        if is_magnet_mode:
                            self._execute_magnet_fire()
                        else:
                            self.mouse.click("left")
                            
                        self.last_trigger_time = time.time()
                        triggering_this_tick = True
        else:
            self.last_filtered_target = None

        # Measure end-to-end processing latency for this cycle
        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        
        # Store preview and telemetry state thread-safely
        with self.lock:
            self.last_frame = screen
            self.last_mask = dilated_mask if dilated_mask is not None else mask
            self.last_target = target_info
            self.is_aiming_now = aiming_this_tick
            self.is_triggering_now = triggering_this_tick
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
        Returns: (frame, mask, target_info, fps, latency_ms, is_aiming_now, is_triggering_now, grabzone)
        """
        with self.lock:
            frame = self.last_frame.copy() if self.last_frame is not None else None
            mask = self.last_mask.copy() if self.last_mask is not None else None
            target = self.last_target.copy()
            fps = self.loop_fps
            latency = self.latency_ms
            is_aiming = self.is_aiming_now
            is_triggering = self.is_triggering_now
            gz = self.grabzone
            
        return frame, mask, target, fps, latency, is_aiming, is_triggering, gz

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
