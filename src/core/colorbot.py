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
    Features the Ultimate Pro Aim Logic:
    1. Multi-Enemy Sticky Target Locking with Spatial Hysteresis.
    2. Adaptive Sigmoid Velocity Curve (Flick -> Smooth Glide -> Micro-Lock).
    3. Natural Spray-Hold Burst & Dynamic Recoil Compensation (RCS).
    4. Silhouette Bridging & True Center-of-Skull Head Targeting.
    5. Sub-pixel EMA Coordinate Dampening for Zero Micro-Jitter.
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

    def __init__(self, x, y, grabzone, color_name="Purple",
                 aim_enabled=False, trigger_enabled=False, magnet_enabled=False,
                 aim_mode="Hold", trigger_mode="Toggle", aim_target="Head",
                 magnet_mode="Burst", burst_count=2, burst_delay=95, burst_cooldown=240, tap_cooldown=180,
                 magnet_target="Head", magnet_fov=45, magnet_smoothing=0.20,
                 sensitivity=0.35, smoothing=0.18, head_offset=7, trigger_delay=20,
                 capture_method="auto", mouse_method="auto"):
        self.x = int(x)
        self.y = int(y)
        self.grabzone = max(10, (int(grabzone) // 2) * 2)
        self.color_name = color_name
        
        # Master switches
        self.aim_enabled = bool(aim_enabled)
        self.trigger_enabled = bool(trigger_enabled)
        self.magnet_enabled = bool(magnet_enabled)
        
        # Aimbot parameters
        self.aim_mode = aim_mode
        self.trigger_mode = trigger_mode
        self.aim_target = aim_target
        self.sensitivity = max(0.01, float(sensitivity))
        self.smoothing = max(0.01, min(1.0, float(smoothing)))
        self.head_offset = int(head_offset)
        self.trigger_delay = max(0, int(trigger_delay)) / 1000.0  # seconds
        
        # Dedicated Magnet parameters
        self.magnet_mode = magnet_mode  # "Burst", "Tap", "Continuous"
        self.burst_count = max(1, int(burst_count))
        self.burst_delay = max(10, int(burst_delay)) / 1000.0  # seconds per bullet in burst
        self.burst_cooldown = max(50, int(burst_cooldown)) / 1000.0  # recovery between bursts
        self.tap_cooldown = max(50, int(tap_cooldown)) / 1000.0  # recovery between taps
        self.magnet_target = magnet_target
        self.magnet_fov = max(10, (int(magnet_fov) // 2) * 2)
        self.magnet_smoothing = max(0.01, min(1.0, float(magnet_smoothing)))

        # Dynamic live key states
        self.is_aim_key_pressed = False
        self.is_trigger_key_pressed = False
        self.is_magnet_key_pressed = False
        self.aim_toggled = False
        self.trigger_toggled = False
        self.magnet_toggled = False

        # Multi-Enemy Target Locking State (Sticky hysteresis)
        self.locked_target_pos = None
        self.locked_target_time = 0.0

        # Spray / Burst & Recoil Compensation States
        self.is_burst_spraying = False
        self.burst_spray_start_time = 0.0
        self.burst_spray_end_time = 0.0
        self.last_burst_end_time = 0.0
        self.last_trigger_time = 0.0
        self.last_tap_time = 0.0

        # Sub-pixel accumulator
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
        if self.is_burst_spraying:
            self.mouse.mouse_up("left")
            self.is_burst_spraying = False
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
        Connects fragmented enemy outline pixels into unified character bounding boxes.
        Includes Multi-Enemy Target Stickiness to prevent target flickering/confusion.
        """
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.close_kernel)
        dilated = cv2.dilate(closed, None, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            self.locked_target_pos = None
            return None, dilated

        boxes = []
        for c in contours:
            if cv2.contourArea(c) >= 12:
                bx, by, bw, bh = cv2.boundingRect(c)
                if bh >= 4 and bw >= 3:
                    boxes.append([bx, by, bx + bw, by + bh])

        if not boxes:
            self.locked_target_pos = None
            return None, dilated

        # Cluster/merge overlapping boxes belonging to the same player body
        merged_boxes = []
        for box in sorted(boxes, key=lambda b: (b[0], b[1])):
            x1, y1, x2, y2 = box
            merged = False
            for m in merged_boxes:
                if not (x2 + 8 < m[0] or x1 - 8 > m[2] or y2 + 8 < m[1] or y1 - 8 > m[3]):
                    m[0] = min(m[0], x1)
                    m[1] = min(m[1], y1)
                    m[2] = max(m[2], x2)
                    m[3] = max(m[3], y2)
                    merged = True
                    break
            if not merged:
                merged_boxes.append([x1, y1, x2, y2])

        # Multi-Enemy Target Stickiness:
        now = time.time()
        has_active_lock = (self.locked_target_pos is not None and (now - self.locked_target_time) < 0.35)
        
        def target_score(b):
            bcx = (b[0] + b[2]) // 2
            bcy = (b[1] + b[3]) // 2
            raw_dist = np.hypot(bcx - gz_center, bcy - gz_center)
            
            if has_active_lock:
                dist_to_prev_lock = np.hypot(bcx - self.locked_target_pos[0], bcy - self.locked_target_pos[1])
                # Stay glued to current enemy with strong hysteresis
                if dist_to_prev_lock < 40:
                    return raw_dist - 35.0
                    
            return raw_dist

        best = min(merged_boxes, key=target_score)
        x = best[0]
        y = best[1]
        w = max(4, best[2] - best[0])
        h = max(6, best[3] - best[1])

        # Update lock position
        self.locked_target_pos = (x + w // 2, y + h // 2)
        self.locked_target_time = now

        return (x, y, w, h), dilated

    def _calculate_target_point(self, x, y, w, h, gz_center, active_bone_setting):
        """
        Calculates the TRUE center of the head/neck/body inside the character model,
        not on the colored outline stroke.
        """
        raw_cX = x + w // 2
        target_mode = active_bone_setting.lower() if active_bone_setting else "head"
        
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
        else: # "head" default
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

    def _calculate_aim_step(self, x_diff, y_diff, dist, smooth_val):
        """
        Ultimate Pro Aim Calculation:
        - Exact Valorant Sens to Pixel Ratio: 1.07437623 * (Sens ^ -0.9936827126).
        - Adaptive Sigmoid Velocity Profile: Smooth acceleration & ease-out deceleration.
        - Dynamic Micro-Deadzone (< 0.9px): Zero shaking.
        """
        if dist < 0.9:
            return 0.0, 0.0

        sens_scale = 1.07437623 * (self.sensitivity ** -0.9936827126)
        target_move_x = x_diff * sens_scale
        target_move_y = y_diff * sens_scale

        smooth = max(0.02, min(1.0, smooth_val))

        # Adaptive Distance Multiplier:
        # - Near target (< 6px): Ease out smoothly into center
        # - Mid target (6 - 25px): Natural human glide
        # - Far target (> 25px): Controlled flick
        if dist < 6.0:
            ease = max(0.18, (dist / 6.0) ** 1.25)
            adaptive_smooth = smooth * ease
        elif dist < 25.0:
            adaptive_smooth = smooth * 1.05
        else:
            adaptive_smooth = min(1.0, smooth * 1.20)

        step_x = target_move_x * adaptive_smooth
        step_y = target_move_y * adaptive_smooth

        # Adaptive Velocity Clamping per tick (Prevents violent whips & robotic flicks)
        max_vel = max(2.5, dist * 0.38 * (smooth + 0.45))
        step_len = np.hypot(step_x, step_y)
        if step_len > max_vel:
            scale = max_vel / step_len
            step_x *= scale
            step_y *= scale

        return step_x, step_y

    def process(self):
        t_start = time.perf_counter()
        now = time.time()
        
        # 1. Manage Active Spray / Burst Duration (Hold Mouse Down)
        if self.is_burst_spraying:
            if now >= self.burst_spray_end_time:
                self.mouse.mouse_up("left")
                self.is_burst_spraying = False
                self.last_burst_end_time = now

        # Screen capture
        screen, frame_id = self.grabber.get_screen_with_id()
        if screen is None or screen.size == 0:
            return

        is_new_frame = (frame_id != self.last_processed_frame_id)
        self.last_processed_frame_id = frame_id

        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = self._get_color_mask(hsv)

        gz_center = self.grabzone // 2
        target_info = {"found": False}
        aiming_this_tick = False
        triggering_this_tick = False

        # Unified character detection with Multi-Enemy Target Locking
        box_data, dilated_mask = self._find_unified_targets(mask, gz_center)

        # Check Active Trigger/Aim/Magnet states
        magnet_is_active = self.magnet_enabled and self.is_magnet_key_pressed
        
        # Reset lock when keys are released
        if not (self.is_aim_key_pressed or self.is_magnet_key_pressed or self.is_trigger_key_pressed):
            self.locked_target_pos = None
            if self.is_burst_spraying:
                self.mouse.mouse_up("left")
                self.is_burst_spraying = False

        if box_data is not None:
            x, y, w, h = box_data
            
            active_bone = self.magnet_target if magnet_is_active else self.aim_target
            cX, target_y = self._calculate_target_point(x, y, w, h, gz_center, active_bone)
            
            x_diff = cX - gz_center
            y_diff = target_y - gz_center

            # Dynamic Recoil Compensation (RCS) during active spray:
            # When gun is actively spraying bullets, pull target slightly downward to counter weapon climb
            if self.is_burst_spraying:
                spray_elapsed = now - self.burst_spray_start_time
                bullet_num = int(spray_elapsed / max(0.05, self.burst_delay)) + 1
                if bullet_num >= 2:
                    recoil_pull = min(4, int(bullet_num * 1.2))
                    y_diff += recoil_pull

            dist = np.hypot(x_diff, y_diff)

            target_info = {
                "found": True,
                "x": x, "y": y, "w": w, "h": h,
                "cX": cX, "cY": y + h // 2,
                "target_y": target_y,
                "x_diff": x_diff, "y_diff": y_diff,
                "dist": round(dist, 1),
                "bone": active_bone
            }

            # 2. Check Aim Control
            should_aim = False
            aim_smooth_val = self.smoothing
            if magnet_is_active:
                should_aim = True
                aim_smooth_val = self.magnet_smoothing
            elif self.aim_enabled:
                if self.aim_mode == "Hold":
                    should_aim = self.is_aim_key_pressed
                elif self.aim_mode == "Toggle":
                    should_aim = self.aim_toggled
                elif self.aim_mode == "Always":
                    should_aim = True

            # 3. Check Standard Triggerbot Control
            should_trigger = False
            if self.trigger_enabled:
                if self.trigger_mode == "Hold":
                    should_trigger = self.is_trigger_key_pressed
                elif self.trigger_mode == "Toggle":
                    should_trigger = self.trigger_toggled
                elif self.trigger_mode == "Always":
                    should_trigger = True

            # Execute Ultimate Pro Aim Step
            if should_aim and is_new_frame:
                step_x, step_y = self._calculate_aim_step(x_diff, y_diff, dist, aim_smooth_val)
                
                self.acc_x += step_x
                self.acc_y += step_y
                
                dx = int(round(self.acc_x))
                dy = int(round(self.acc_y))
                
                if dx != 0 or dy != 0:
                    self.acc_x -= dx
                    self.acc_y -= dy
                    self.mouse.move(dx, dy)
                    aiming_this_tick = True

            # 4. Magnet Firing Execution (Burst = Hold Spray, Tap = Single Shot)
            hitbox_w = max(4, w // 2)
            hitbox_h = max(5, int(h * 0.35))
            is_on_target = (abs(cX - gz_center) <= hitbox_w and abs(target_y - gz_center) <= hitbox_h)

            if magnet_is_active:
                mode_str = self.magnet_mode.lower() if self.magnet_mode else "burst"
                
                if "burst" in mode_str:
                    if is_on_target and not self.is_burst_spraying:
                        if now - self.last_burst_end_time >= (self.trigger_delay + self.burst_cooldown):
                            if self.trigger_delay > 0:
                                time.sleep(self.trigger_delay)
                            
                            spray_duration = max(0.06, self.burst_count * self.burst_delay)
                            self.mouse.mouse_down("left")
                            self.is_burst_spraying = True
                            self.burst_spray_start_time = time.time()
                            self.burst_spray_end_time = self.burst_spray_start_time + spray_duration
                            triggering_this_tick = True
                
                elif "continuous" in mode_str or "spray" in mode_str:
                    if is_on_target and not self.is_burst_spraying:
                        self.mouse.mouse_down("left")
                        self.is_burst_spraying = True
                        self.burst_spray_start_time = time.time()
                    elif not is_on_target and self.is_burst_spraying:
                        self.mouse.mouse_up("left")
                        self.is_burst_spraying = False
                    triggering_this_tick = self.is_burst_spraying

                else: # "tap" mode
                    if is_on_target:
                        if now - self.last_tap_time >= (self.trigger_delay + self.tap_cooldown):
                            if self.trigger_delay > 0:
                                time.sleep(self.trigger_delay)
                            self.mouse.click("left", delay=0.015)
                            self.last_tap_time = time.time()
                            triggering_this_tick = True

            # 5. Standard Triggerbot Execution
            elif should_trigger and is_on_target:
                if now - self.last_trigger_time >= (self.trigger_delay + 0.12):
                    if self.trigger_delay > 0:
                        time.sleep(self.trigger_delay)
                    self.mouse.click("left")
                    self.last_trigger_time = time.time()
                    triggering_this_tick = True
        else:
            self.last_filtered_target = None
            if self.is_burst_spraying and "continuous" in self.magnet_mode.lower():
                self.mouse.mouse_up("left")
                self.is_burst_spraying = False

        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        
        with self.lock:
            self.last_frame = screen
            self.last_mask = dilated_mask if dilated_mask is not None else mask
            self.last_target = target_info
            self.is_aiming_now = aiming_this_tick
            self.is_triggering_now = triggering_this_tick or self.is_burst_spraying
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
