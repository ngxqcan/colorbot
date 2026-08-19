import sys
import math
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
                 anti_shake_enabled=True, deadzone=1.0,
                 rcs_enabled=True, rcs_pitch=2.5, rcs_yaw=0.0, rcs_start_delay_ms=100,
                 kmnet_ip="192.168.2.188", kmnet_port=16896, kmnet_uuid="46405c53",
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
        
        # Anti-Shake & Micro-Deadzone
        self.anti_shake_enabled = bool(anti_shake_enabled)
        self.deadzone = max(0.5, float(deadzone))

        # Recoil Control System (RCS)
        self.rcs_enabled = bool(rcs_enabled)
        self.rcs_pitch = float(rcs_pitch)
        self.rcs_yaw = float(rcs_yaw)
        self.rcs_start_delay_ms = float(rcs_start_delay_ms)
        
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

        # Moving Shoot: Velocity Tracking & Target Lead Predictor
        self.target_vel_x = 0.0
        self.target_vel_y = 0.0
        self.last_target_time = 0.0
        self.last_raw_target = None

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

        self.mouse = PicoMouse(method=mouse_method, kmnet_ip=kmnet_ip, kmnet_port=kmnet_port, kmnet_uuid=kmnet_uuid)
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
        Calculates exact bone points (Head, Neck, Shoulder, Body) inside the character model,
        and applies dynamic velocity lead prediction & continuous sigmoid stabilization for Moving Shoot.
        """
        now = time.time()
        center_x = x + w // 2
        
        # 1. Head Bone
        head_off = min(self.head_offset, max(3, int(h * 0.15)))
        head_pt = (center_x, y + head_off)
        
        # 2. Neck Bone
        neck_off = max(head_off + 2, int(h * 0.25))
        neck_pt = (center_x, y + neck_off)
        
        # 3. Shoulder Bones
        shoulder_y = y + int(h * 0.32)
        l_shoulder_pt = (x + max(1, int(w * 0.22)), shoulder_y)
        r_shoulder_pt = (x + min(w - 2, int(w * 0.78)), shoulder_y)
        c_shoulder_pt = (center_x, shoulder_y)
        shoulders = [l_shoulder_pt, r_shoulder_pt, c_shoulder_pt]
        closest_shoulder = min(shoulders, key=lambda p: np.hypot(p[0] - gz_center, p[1] - gz_center))
        
        # 4. Body / Chest Bone
        body_y = y + int(h * 0.48)
        body_pt = (center_x, body_y)
        
        bones_dict = {
            "head": head_pt,
            "neck": neck_pt,
            "shoulder_left": l_shoulder_pt,
            "shoulder_right": r_shoulder_pt,
            "shoulder_center": c_shoulder_pt,
            "shoulder": closest_shoulder,
            "body": body_pt
        }

        target_mode = active_bone_setting.lower() if active_bone_setting else "head"
        if "shoulder" in target_mode:
            raw_cX, raw_target_y = closest_shoulder
            active_name = "Shoulder"
        elif "neck" in target_mode:
            raw_cX, raw_target_y = neck_pt
            active_name = "Neck"
        elif "body" in target_mode or "chest" in target_mode:
            raw_cX, raw_target_y = body_pt
            active_name = "Body"
        elif "auto" in target_mode:
            candidates = [("Head", head_pt), ("Neck", neck_pt), ("Shoulder", closest_shoulder), ("Body", body_pt)]
            active_name, (raw_cX, raw_target_y) = min(candidates, key=lambda item: np.hypot(item[1][0] - gz_center, item[1][1] - gz_center))
        else:
            raw_cX, raw_target_y = head_pt
            active_name = "Head"

        # Moving Shoot: Dynamic Velocity & Motion Lead Calculation
        lead_x = 0.0
        lead_y = 0.0
        if self.last_raw_target is not None and self.last_target_time > 0:
            dt = max(0.001, min(0.08, now - self.last_target_time))
            raw_vx = (raw_cX - self.last_raw_target[0]) / dt
            raw_vy = (raw_target_y - self.last_raw_target[1]) / dt
            
            # Smooth velocity EMA filter
            self.target_vel_x = 0.60 * self.target_vel_x + 0.40 * raw_vx
            self.target_vel_y = 0.60 * self.target_vel_y + 0.40 * raw_vy
            
            # Predictive lead compensation for frame/capture latency (~16ms)
            lead_x = self.target_vel_x * 0.016
            lead_y = self.target_vel_y * 0.016

        self.last_raw_target = (raw_cX, raw_target_y)
        self.last_target_time = now

        target_with_lead_x = raw_cX + lead_x
        target_with_lead_y = raw_target_y + lead_y

        # Continuous Sigmoid Anti-Shake filter (prevents micro-jitter and motion stutter)
        if self.anti_shake_enabled and self.last_filtered_target is not None:
            prev_x, prev_y = self.last_filtered_target
            delta_dist = np.hypot(target_with_lead_x - prev_x, target_with_lead_y - prev_y)
            # Continuous Sigmoidal blending (rock-solid when still, zero-lag tracking when running)
            alpha = 0.22 + 0.78 / (1.0 + np.exp(-(delta_dist - 5.5) / 2.0))
            filtered_x = prev_x * (1.0 - alpha) + float(target_with_lead_x) * alpha
            filtered_y = prev_y * (1.0 - alpha) + float(target_with_lead_y) * alpha
        else:
            filtered_x = float(target_with_lead_x)
            filtered_y = float(target_with_lead_y)

        self.last_filtered_target = (filtered_x, filtered_y)
        cX = int(round(filtered_x))
        target_y = int(round(filtered_y))
        return cX, target_y, bones_dict, active_name

    def _calculate_aim_step(self, x_diff, y_diff, dist, smooth_val):
        """
        Ultimate Pro Aim Calculation for Moving Shoot:
        - Exact Valorant Sens to Pixel Ratio: 1.07437623 * (Sens ^ -0.9936827126).
        - Soft Hermite Deadzone: Smooth ease-in, zero shaking and zero boundary stutter.
        - Dynamic Velocity Clamping with Motion Feedforward.
        """
        if dist <= 0.4:
            return 0.0, 0.0

        # Soft Deadzone curve: smooth ease-in from 0 to 1 without hard cutoffs
        if dist < self.deadzone:
            t = dist / max(0.5, self.deadzone)
            dz_mult = t * t * (3.0 - 2.0 * t)
        else:
            dz_mult = 1.0

        sens_scale = 1.07437623 * (self.sensitivity ** -0.9936827126)
        target_move_x = x_diff * sens_scale
        target_move_y = y_diff * sens_scale

        smooth = max(0.02, min(1.0, smooth_val))

        # Adaptive Distance Multiplier:
        if dist < 5.0:
            ease = max(0.20, (dist / 5.0) ** 1.20)
            adaptive_smooth = smooth * ease
        elif dist < 22.0:
            adaptive_smooth = smooth * 1.0
        else:
            adaptive_smooth = min(1.0, smooth * 1.15)

        step_x = target_move_x * adaptive_smooth * dz_mult
        step_y = target_move_y * adaptive_smooth * dz_mult

        # Dynamic Velocity Clamping per tick (allows fast tracking when player is moving shoot)
        target_speed = np.hypot(self.target_vel_x, self.target_vel_y)
        max_vel = max(2.8, (dist * 0.42 + target_speed * 0.02) * (smooth + 0.40))
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
        
        # Reset lock and accumulator when keys are released
        if not (self.is_aim_key_pressed or self.is_magnet_key_pressed or self.is_trigger_key_pressed):
            self.locked_target_pos = None
            self.acc_x = 0.0
            self.acc_y = 0.0
            if self.is_burst_spraying:
                self.mouse.mouse_up("left")
                self.is_burst_spraying = False

        if box_data is not None:
            x, y, w, h = box_data
            
            active_bone_req = self.magnet_target if magnet_is_active else self.aim_target
            cX, target_y, bones_dict, active_bone_name = self._calculate_target_point(x, y, w, h, gz_center, active_bone_req)
            
            # Moving Shoot: Recoil Curve during Burst / Spray
            # In Valorant:
            # Bullet 1 (0ms - 90ms): Exact First-Bullet Accuracy -> Pinpoint on Head/Neck
            # Bullet 2 (90ms - 180ms): Recoil climbs slightly -> Pull down smoothly by rcs_pitch * 0.75
            # Bullet 3 (180ms - 270ms): Recoil reaches burst peak -> Pull down smoothly by rcs_pitch * 1.6
            # Bullet 4+ (Continuous Spray): Lock onto upper chest with sinusoidal yaw stabilization
            if self.rcs_enabled and self.is_burst_spraying:
                spray_elapsed_ms = (now - self.burst_spray_start_time) * 1000.0
                if spray_elapsed_ms >= self.rcs_start_delay_ms:
                    spray_t = (spray_elapsed_ms - self.rcs_start_delay_ms) / 1000.0
                    
                    # Sigmoidal smooth progressive pull-down
                    burst_duration = max(0.15, self.burst_count * self.burst_delay)
                    burst_progress = min(1.0, spray_t / burst_duration)
                    recoil_scale = burst_progress * burst_progress * (3.0 - 2.0 * burst_progress)
                    
                    max_recoil_offset = min(int(h * 0.38), int(self.rcs_pitch * 3.8))
                    recoil_pull_y = recoil_scale * max_recoil_offset
                    target_y += int(round(recoil_pull_y))

                    # Subtle horizontal counter-sway for moving recoil stability
                    if self.rcs_yaw > 0.01:
                        yaw_sway = math.sin(spray_t * 12.0) * self.rcs_yaw * min(1.0, spray_t * 2.5)
                        cX += int(round(yaw_sway))

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
                "bone": active_bone_name,
                "bones": bones_dict
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
                
                self.acc_x = max(-2.0, min(2.0, self.acc_x + step_x))
                self.acc_y = max(-2.0, min(2.0, self.acc_y + step_y))
                
                dx = int(round(self.acc_x))
                dy = int(round(self.acc_y))
                
                if dx != 0 or dy != 0:
                    self.acc_x -= dx
                    self.acc_y -= dy
                    self.mouse.move(dx, dy)
                    aiming_this_tick = True

            # 4. Magnet Firing Execution with Dynamic Velocity-Aware Hitbox Window
            hitbox_w = max(5, int(w * 0.42) + int(abs(self.target_vel_x) * 0.015))
            hitbox_h = max(6, int(h * 0.35))
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
