import sys
import time
import cv2
import numpy as np
from PIL import Image, ImageTk
import customtkinter
from threading import Thread

from core.colorbot import Colorbot
from utils.config_manager import ConfigManager
from utils.input_handler import is_key_pressed, record_key_or_mouse

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()  

        self.config_manager = ConfigManager()
        self._init_variables()
        self._setup_ui()
        
        # Popout window handle
        self.popout_window = None
        self.popout_label = None

        # Start key listener background thread
        self.listener_running = True
        self.listener_thread = Thread(target=self._listen_for_keys, daemon=True)
        self.listener_thread.start()

        # Start UI preview update loop (30 FPS)
        self._update_preview_loop()

    def _init_variables(self):
        # Master hotkey
        self.master_toggle_key = self.config_manager.get('MASTER_TOGGLE_KEY', 'f1')
        
        # Aimbot variables
        self.aim_enabled = bool(self.config_manager.get('AIM_ENABLED', False))
        self.aim_key = self.config_manager.get('AIM_KEY', 'RMB')
        self.aim_mode = self.config_manager.get('AIM_MODE', 'Hold')
        self.aim_target = self.config_manager.get('AIM_TARGET', 'Head')
        self.magnet_mode = self.config_manager.get('MAGNET_MODE', 'Tap')
        self.burst_count = int(self.config_manager.get('BURST_COUNT', 2))
        self.burst_delay = int(self.config_manager.get('BURST_DELAY', 80))
        self.fov = float(self.config_manager.get('FOV', 45))
        self.shared_color = self.config_manager.get('ENEMY_COLOR', 'Purple')
        self.sensitivity = float(self.config_manager.get('SENSITIVITY', 0.35))
        self.smoothing = float(self.config_manager.get('SMOOTHING', 0.18))
        self.head_offset = int(self.config_manager.get('HEAD_OFFSET', 7))

        # Triggerbot variables
        self.trigger_enabled = bool(self.config_manager.get('TRIGGER_ENABLED', False))
        self.trigger_key = self.config_manager.get('TRIGGER_KEY', 'f2')
        self.trigger_mode = self.config_manager.get('TRIGGER_MODE', 'Toggle')
        self.trigger_delay = float(self.config_manager.get('TRIGGER_DELAY', 30))

        # Misc variables
        self.resolution = self.config_manager.get('RESOLUTION', [1920, 1080])
        self.capture_method = self.config_manager.get('CAPTURE_METHOD', 'Auto')
        self.mouse_method = self.config_manager.get('MOUSE_METHOD', 'Auto')
        self.formatted_resolution = f"{self.resolution[0]}x{self.resolution[1]}"

        # Preview variables (Configurable size: 360x360 default)
        self.preview_enabled = True
        self.preview_mode = self.config_manager.get('PREVIEW_MODE', 'Camera + HUD')
        self.preview_size_str = self.config_manager.get('PREVIEW_SIZE', '360x360')
        self.preview_dim = 360

        self.is_recording_key = False
        self.colorbot = None
        self.current_frame_img = None

    def _setup_ui(self):
        self.resizable(False, False)
        self.title("Valorant Colorbot - 1PC Pro Engine")
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        self.geometry("980x560")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar Frame
        self.sidebar_frame = customtkinter.CTkFrame(self, width=170, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=6, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)
        
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame, 
            text="⚡ COLORBOT", 
            font=customtkinter.CTkFont(size=18, weight="bold"),
            text_color="#38bdf8"
        )
        self.logo_label.grid(row=0, column=0, padx=15, pady=(20, 15))

        self.sidebar_button_1 = customtkinter.CTkButton(
            self.sidebar_frame, text="🎯 Aimbot", 
            command=lambda: self.show_frame(self.aimbot_frame),
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        self.sidebar_button_1.grid(row=1, column=0, padx=12, pady=6)

        self.sidebar_button_2 = customtkinter.CTkButton(
            self.sidebar_frame, text="⚡ Triggerbot", 
            command=lambda: self.show_frame(self.triggerbot_frame),
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        self.sidebar_button_2.grid(row=2, column=0, padx=12, pady=6)

        self.sidebar_button_3 = customtkinter.CTkButton(
            self.sidebar_frame, text="👁️ Live Preview", 
            command=lambda: self.show_frame(self.preview_frame),
            font=customtkinter.CTkFont(size=13, weight="bold"),
            fg_color="#0284c7", hover_color="#0369a1"
        )
        self.sidebar_button_3.grid(row=3, column=0, padx=12, pady=6)

        self.sidebar_button_4 = customtkinter.CTkButton(
            self.sidebar_frame, text="⚙️ Settings", 
            command=lambda: self.show_frame(self.misc_frame),
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        self.sidebar_button_4.grid(row=4, column=0, padx=12, pady=6)

        # Status Badges
        self.status_container = customtkinter.CTkFrame(self.sidebar_frame, fg_color="#18181b", corner_radius=8)
        self.status_container.grid(row=6, column=0, padx=10, pady=15, sticky="s")
        
        self.status_label = customtkinter.CTkLabel(
            self.status_container, 
            text="● Engine: Standby", 
            text_color="#71717a",
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.status_label.pack(padx=8, pady=(6, 2))

        self.aim_status_badge = customtkinter.CTkLabel(
            self.status_container, 
            text="Aim: IDLE", 
            text_color="#a1a1aa",
            font=customtkinter.CTkFont(size=10)
        )
        self.aim_status_badge.pack(padx=8, pady=(0, 6))

        # Content Container
        self.content_frame = customtkinter.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, rowspan=6, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.aimbot_frame = customtkinter.CTkFrame(self.content_frame)
        self.triggerbot_frame = customtkinter.CTkFrame(self.content_frame)
        self.preview_frame = customtkinter.CTkFrame(self.content_frame)
        self.misc_frame = customtkinter.CTkFrame(self.content_frame)

        for frame in (self.aimbot_frame, self.triggerbot_frame, self.preview_frame, self.misc_frame):
            frame.grid(row=0, column=0, sticky="nsew")

        self._setup_aimbot_page()
        self._setup_triggerbot_page()
        self._setup_preview_page()
        self._setup_misc_page()
        
        self.show_frame(self.aimbot_frame)

    def _setup_aimbot_page(self):
        # Row 0: Master Switch & Hotkey & Presets
        top_bar = customtkinter.CTkFrame(self.aimbot_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, columnspan=4, padx=10, pady=(6, 4), sticky="ew")

        self.switch_aim = customtkinter.CTkSwitch(
            top_bar, text="Aimbot Master", 
            font=customtkinter.CTkFont(size=14, weight="bold"), 
            command=self.toggle_aim_master
        )
        self.switch_aim.pack(side="left", padx=5)
        if self.aim_enabled:
            self.switch_aim.select()

        # Preset Quick Buttons
        preset_box = customtkinter.CTkFrame(top_bar, fg_color="#18181b", corner_radius=6)
        preset_box.pack(side="left", padx=10)
        
        customtkinter.CTkLabel(preset_box, text="Presets:", font=customtkinter.CTkFont(size=11, weight="bold"), text_color="#71717a").pack(side="left", padx=(6, 3), pady=2)
        
        customtkinter.CTkButton(
            preset_box, text="🎯 Legit", width=52, height=22,
            command=lambda: self.apply_preset("legit"),
            font=customtkinter.CTkFont(size=11), fg_color="#059669", hover_color="#047857"
        ).pack(side="left", padx=2, pady=2)
        
        customtkinter.CTkButton(
            preset_box, text="🧲 Mag Tap", width=65, height=22,
            command=lambda: self.apply_preset("mag_tap"),
            font=customtkinter.CTkFont(size=11), fg_color="#0284c7", hover_color="#0369a1"
        ).pack(side="left", padx=2, pady=2)

        customtkinter.CTkButton(
            preset_box, text="💥 Mag Burst", width=70, height=22,
            command=lambda: self.apply_preset("mag_burst"),
            font=customtkinter.CTkFont(size=11), fg_color="#7c3aed", hover_color="#6d28d9"
        ).pack(side="left", padx=2, pady=2)

        customtkinter.CTkButton(
            preset_box, text="⚡ Rage", width=50, height=22,
            command=lambda: self.apply_preset("rage"),
            font=customtkinter.CTkFont(size=11), fg_color="#dc2626", hover_color="#b91c1c"
        ).pack(side="left", padx=(2, 6), pady=2)

        self.button_master_hotkey = customtkinter.CTkButton(
            top_bar, text=f"Hotkey: {self.master_toggle_key.upper()}", 
            command=lambda: self.change_key_text("master"), 
            width=95, height=26, font=customtkinter.CTkFont(size=11)
        )
        self.button_master_hotkey.pack(side="right", padx=5)

        # Row 1: Key, Mode, Magnet Fire, Bone Target, Enemy Color
        row1 = customtkinter.CTkFrame(self.aimbot_frame, fg_color="#18181b", corner_radius=8)
        row1.grid(row=1, column=0, columnspan=4, padx=10, pady=4, sticky="ew")

        customtkinter.CTkLabel(row1, text="Key:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 3), pady=6)
        self.button_aim_key = customtkinter.CTkButton(
            row1, text=f"{self.aim_key}", 
            command=lambda: self.change_key_text("aim"), 
            width=75, height=26, font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.button_aim_key.pack(side="left", padx=3, pady=6)

        customtkinter.CTkLabel(row1, text="Mode:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(6, 3), pady=6)
        self.combobox_aim_mode = customtkinter.CTkComboBox(
            row1, values=["Hold", "Magnet", "Toggle", "Always"], 
            command=self.aim_mode_callback, width=85, height=26,
            font=customtkinter.CTkFont(size=12)
        )
        self.combobox_aim_mode.pack(side="left", padx=3, pady=6)
        self.combobox_aim_mode.set(self.aim_mode)

        customtkinter.CTkLabel(row1, text="Magnet Fire:", font=customtkinter.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(side="left", padx=(6, 3), pady=6)
        self.combobox_magnet_fire = customtkinter.CTkComboBox(
            row1, values=["Tap", "Burst (2-Shot)", "Burst (3-Shot)", "Continuous"], 
            command=self.magnet_fire_callback, width=110, height=26,
            font=customtkinter.CTkFont(size=11)
        )
        self.combobox_magnet_fire.pack(side="left", padx=3, pady=6)
        self.combobox_magnet_fire.set(self.magnet_mode)

        customtkinter.CTkLabel(row1, text="Bone:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(6, 3), pady=6)
        self.combobox_aim_target = customtkinter.CTkComboBox(
            row1, values=["Head", "Neck", "Body", "Auto"], 
            command=self.aim_target_callback, width=75, height=26,
            font=customtkinter.CTkFont(size=12)
        )
        self.combobox_aim_target.pack(side="left", padx=3, pady=6)
        self.combobox_aim_target.set(self.aim_target)

        customtkinter.CTkLabel(row1, text="Color:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(6, 3), pady=6)
        self.combobox_aim_color = customtkinter.CTkComboBox(
            row1, values=["Purple", "Yellow", "Red"], 
            command=self.color_change_callback, width=80, height=26,
            font=customtkinter.CTkFont(size=12)
        )
        self.combobox_aim_color.pack(side="left", padx=(3, 8), pady=6)
        self.combobox_aim_color.set(self.shared_color)

        # Row 2: FOV Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="FOV (Capture Box):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.slider_aim_FOV = customtkinter.CTkSlider(self.aimbot_frame, from_=20, to=250, command=self.FOV_slider_callback)
        self.slider_aim_FOV.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.slider_aim_FOV.set(self.fov)
        self.label_aim_FOV_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.fov)))
        self.label_aim_FOV_value.grid(row=2, column=3, padx=5, pady=5)

        # Row 3: Sensitivity Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="In-Game Sensitivity:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.slider_sens = customtkinter.CTkSlider(self.aimbot_frame, from_=0.05, to=1.5, command=self.sens_slider_callback)
        self.slider_sens.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.slider_sens.set(self.sensitivity)
        self.label_sens_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=f"{self.sensitivity:.2f}")
        self.label_sens_value.grid(row=3, column=3, padx=5, pady=5)

        # Row 4: Smoothing Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="Smoothing Factor:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.slider_smooth = customtkinter.CTkSlider(self.aimbot_frame, from_=0.05, to=1.0, command=self.smooth_slider_callback)
        self.slider_smooth.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.slider_smooth.set(self.smoothing)
        self.label_smooth_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=f"{self.smoothing:.2f}")
        self.label_smooth_value.grid(row=4, column=3, padx=5, pady=5)

        # Row 5: Head Offset Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="Head Y-Offset:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.slider_head = customtkinter.CTkSlider(self.aimbot_frame, from_=0, to=25, command=self.head_slider_callback)
        self.slider_head.grid(row=5, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.slider_head.set(self.head_offset)
        self.label_head_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.head_offset)))
        self.label_head_value.grid(row=5, column=3, padx=5, pady=5)

    def _setup_triggerbot_page(self):
        # Row 0: Master Switch
        top_bar = customtkinter.CTkFrame(self.triggerbot_frame, fg_color="transparent")
        top_bar.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        self.switch_trigger = customtkinter.CTkSwitch(
            top_bar, text="Triggerbot Master Enable", 
            font=customtkinter.CTkFont(size=14, weight="bold"), 
            command=self.toggle_trigger_master
        )
        self.switch_trigger.pack(side="left", padx=5)
        if self.trigger_enabled:
            self.switch_trigger.select()

        # Row 1: Key, Mode, Color
        row1 = customtkinter.CTkFrame(self.triggerbot_frame, fg_color="#18181b", corner_radius=8)
        row1.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")

        customtkinter.CTkLabel(row1, text="Trigger Key:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.button_trigger_key = customtkinter.CTkButton(
            row1, text=f"{self.trigger_key}", 
            command=lambda: self.change_key_text("trigger"), 
            width=100, font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.button_trigger_key.pack(side="left", padx=4, pady=8)

        customtkinter.CTkLabel(row1, text="Mode:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(12, 4), pady=8)
        self.combobox_trigger_mode = customtkinter.CTkComboBox(
            row1, values=["Toggle", "Hold", "Always"], 
            command=self.trigger_mode_callback, width=95,
            font=customtkinter.CTkFont(size=12)
        )
        self.combobox_trigger_mode.pack(side="left", padx=4, pady=8)
        self.combobox_trigger_mode.set(self.trigger_mode)

        customtkinter.CTkLabel(row1, text="Color:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(12, 4), pady=8)
        self.combobox_trigger_color = customtkinter.CTkComboBox(
            row1, values=["Purple", "Yellow", "Red"], 
            command=self.color_change_callback, width=100,
            font=customtkinter.CTkFont(size=12)
        )
        self.combobox_trigger_color.pack(side="left", padx=4, pady=8)
        self.combobox_trigger_color.set(self.shared_color)

        # Row 2: Delay Slider
        customtkinter.CTkLabel(self.triggerbot_frame, text="Shot Delay (ms):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=2, column=0, padx=10, pady=15, sticky="w")
        self.slider_trigger_delay = customtkinter.CTkSlider(self.triggerbot_frame, from_=0, to=200, command=self.delay_slider_callback)
        self.slider_trigger_delay.grid(row=2, column=1, padx=5, pady=15, sticky="ew")
        self.slider_trigger_delay.set(self.trigger_delay)
        self.label_trigger_delay_value = customtkinter.CTkLabel(self.triggerbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.trigger_delay)))
        self.label_trigger_delay_value.grid(row=2, column=2, padx=5, pady=15)

    def _setup_preview_page(self):
        # Top toolbar
        toolbar = customtkinter.CTkFrame(self.preview_frame, fg_color="#18181b", corner_radius=8)
        toolbar.pack(fill="x", padx=10, pady=(6, 4))

        self.switch_preview = customtkinter.CTkSwitch(
            toolbar, text="Stream Live", 
            font=customtkinter.CTkFont(size=12, weight="bold"), 
            command=self.toggle_preview_stream
        )
        self.switch_preview.pack(side="left", padx=8, pady=6)
        if self.preview_enabled:
            self.switch_preview.select()

        customtkinter.CTkLabel(toolbar, text="View:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 3), pady=6)
        self.combobox_preview_mode = customtkinter.CTkComboBox(
            toolbar, values=["Camera + HUD", "HSV Color Mask", "Split View"], 
            command=self.preview_mode_callback, width=125, height=26,
            font=customtkinter.CTkFont(size=11)
        )
        self.combobox_preview_mode.pack(side="left", padx=3, pady=6)
        self.combobox_preview_mode.set(self.preview_mode)

        customtkinter.CTkLabel(toolbar, text="Size:", font=customtkinter.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 3), pady=6)
        self.combobox_preview_size = customtkinter.CTkComboBox(
            toolbar, values=["360x360", "320x320", "400x400", "256x256"], 
            command=self.preview_size_callback, width=95, height=26,
            font=customtkinter.CTkFont(size=11)
        )
        self.combobox_preview_size.pack(side="left", padx=3, pady=6)
        self.combobox_preview_size.set(self.preview_size_str)

        # Quick FOV adjustment directly on Preview Page
        customtkinter.CTkLabel(toolbar, text="FOV:", font=customtkinter.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(side="left", padx=(8, 3), pady=6)
        self.slider_preview_fov = customtkinter.CTkSlider(toolbar, from_=20, to=200, width=100, command=self.FOV_slider_callback)
        self.slider_preview_fov.pack(side="left", padx=3, pady=6)
        self.slider_preview_fov.set(self.fov)

        self.btn_popout = customtkinter.CTkButton(
            toolbar, text="↗ Popout", 
            command=self.toggle_popout_window,
            width=80, height=26,
            font=customtkinter.CTkFont(size=11, weight="bold"),
            fg_color="#059669", hover_color="#047857"
        )
        self.btn_popout.pack(side="right", padx=8, pady=6)

        # Main Display Area Container
        display_outer = customtkinter.CTkFrame(self.preview_frame, fg_color="#09090b", corner_radius=8)
        display_outer.pack(fill="both", expand=True, padx=10, pady=4)

        # Preview box
        self.preview_box = customtkinter.CTkFrame(display_outer, width=self.preview_dim, height=self.preview_dim, fg_color="#000000", corner_radius=6)
        self.preview_box.pack(expand=True, pady=4)
        self.preview_box.pack_propagate(False)

        self.preview_label = customtkinter.CTkLabel(
            self.preview_box, 
            text="[ Live HD Canvas Initializing... ]",
            text_color="#71717a",
            font=customtkinter.CTkFont(size=13)
        )
        self.preview_label.pack(expand=True, fill="both")

        # Bottom Telemetry Bar (FPS, Latency, Target, Delta)
        self.telemetry_bar = customtkinter.CTkFrame(self.preview_frame, fg_color="#18181b", height=32, corner_radius=6)
        self.telemetry_bar.pack(fill="x", padx=10, pady=(2, 6))

        self.lbl_target_status = customtkinter.CTkLabel(
            self.telemetry_bar, 
            text="Target: SEARCHING", 
            text_color="#fbbf24",
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.lbl_target_status.pack(side="left", padx=10, pady=4)

        self.lbl_target_delta = customtkinter.CTkLabel(
            self.telemetry_bar, 
            text="dX: 0px | dY: 0px (Dist: 0px)", 
            text_color="#a1a1aa",
            font=customtkinter.CTkFont(size=11)
        )
        self.lbl_target_delta.pack(side="left", padx=10, pady=4)

        self.lbl_fov_live = customtkinter.CTkLabel(
            self.telemetry_bar, 
            text=f"FOV: {int(self.fov)}px", 
            text_color="#38bdf8",
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.lbl_fov_live.pack(side="left", padx=12, pady=4)

        self.lbl_fps_stat = customtkinter.CTkLabel(
            self.telemetry_bar, 
            text="FPS: 0", 
            text_color="#38bdf8",
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.lbl_fps_stat.pack(side="right", padx=(4, 10), pady=4)

        self.lbl_latency_stat = customtkinter.CTkLabel(
            self.telemetry_bar, 
            text="⚡ 0.00 ms", 
            text_color="#22c55e",
            font=customtkinter.CTkFont(size=11, weight="bold")
        )
        self.lbl_latency_stat.pack(side="right", padx=(10, 4), pady=4)

    def _setup_misc_page(self):
        # Row 0: Resolution
        customtkinter.CTkLabel(self.misc_frame, text="Screen Resolution:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.resolution_input = customtkinter.CTkEntry(self.misc_frame, width=140, font=customtkinter.CTkFont(size=13))
        self.resolution_input.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.resolution_input.insert(0, self.formatted_resolution)

        # Row 1: Screen Capture Driver
        customtkinter.CTkLabel(self.misc_frame, text="Capture Driver (1-PC):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.combobox_capture = customtkinter.CTkComboBox(
            self.misc_frame, values=["Auto", "DXCam", "MSS", "GDI", "NDI"], 
            width=140, font=customtkinter.CTkFont(size=13)
        )
        self.combobox_capture.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        self.combobox_capture.set(self.capture_method)

        # Row 2: Mouse Driver
        customtkinter.CTkLabel(self.misc_frame, text="Mouse Driver (1-PC):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.combobox_mouse = customtkinter.CTkComboBox(
            self.misc_frame, values=["Auto", "Logitech", "Makcu", "Win32"], 
            width=140, font=customtkinter.CTkFont(size=13)
        )
        self.combobox_mouse.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        self.combobox_mouse.set(self.mouse_method)

        # Row 3: Buttons
        btn_frame = customtkinter.CTkFrame(self.misc_frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=15)
        customtkinter.CTkButton(btn_frame, text="Load Config", command=self.load_config, width=120, font=customtkinter.CTkFont(size=13)).pack(side="left", padx=10)
        customtkinter.CTkButton(btn_frame, text="Save Config", command=self.save_config, width=120, font=customtkinter.CTkFont(size=13)).pack(side="left", padx=10)

    def show_frame(self, frame):
        frame.tkraise()

    def preview_size_callback(self, new_size_str):
        self.preview_size_str = new_size_str
        try:
            dim = int(new_size_str.split('x')[0])
            self.preview_dim = dim
            self.preview_box.configure(width=dim, height=dim)
        except Exception:
            pass

    def apply_preset(self, preset_name):
        """Applies legit, magnet tap, magnet burst, or rage preset configuration."""
        if preset_name == "legit":
            self.fov = 45
            self.smoothing = 0.18
            self.aim_target = "Head"
            self.aim_mode = "Hold"
            self.magnet_mode = "Tap"
            self.head_offset = 7
            self.trigger_delay = 35
        elif preset_name == "mag_tap":
            self.fov = 45
            self.smoothing = 0.20
            self.aim_target = "Head"
            self.aim_mode = "Magnet"
            self.magnet_mode = "Tap"
            self.head_offset = 7
            self.trigger_delay = 25
        elif preset_name == "mag_burst":
            self.fov = 45
            self.smoothing = 0.20
            self.aim_target = "Head"
            self.aim_mode = "Magnet"
            self.magnet_mode = "Burst (2-Shot)"
            self.head_offset = 7
            self.trigger_delay = 25
        elif preset_name == "rage":
            self.fov = 85
            self.smoothing = 0.45
            self.aim_target = "Head"
            self.aim_mode = "Hold"
            self.head_offset = 8
            self.trigger_delay = 20

        # Update sliders & comboboxes
        self.slider_aim_FOV.set(self.fov)
        self.slider_preview_fov.set(self.fov)
        self.label_aim_FOV_value.configure(text=str(int(self.fov)))
        self.lbl_fov_live.configure(text=f"FOV: {int(self.fov)}px")
        self.slider_smooth.set(self.smoothing)
        self.label_smooth_value.configure(text=f"{self.smoothing:.2f}")
        self.slider_head.set(self.head_offset)
        self.label_head_value.configure(text=str(self.head_offset))
        self.slider_trigger_delay.set(self.trigger_delay)
        self.label_trigger_delay_value.configure(text=str(int(self.trigger_delay)))
        self.combobox_aim_target.set(self.aim_target)
        self.combobox_aim_mode.set(self.aim_mode)
        self.combobox_magnet_fire.set(self.magnet_mode)

        if self.colorbot:
            self.colorbot.smoothing = self.smoothing
            self.colorbot.aim_target = self.aim_target
            self.colorbot.aim_mode = self.aim_mode
            self.colorbot.magnet_mode = self.magnet_mode
            self.colorbot.head_offset = self.head_offset
            self.colorbot.trigger_delay = self.trigger_delay / 1000.0
            try:
                res_parts = self.resolution_input.get().split('x')
                w, h = int(res_parts[0]), int(res_parts[1])
            except Exception:
                w, h = 1920, 1080
            cx, cy = w // 2, h // 2
            self.colorbot.update_roi(cx, cy, self.fov)

        self.save_config()
        self.status_label.configure(text=f"● Preset '{preset_name.replace('_', ' ').title()}' Applied!", text_color="#38bdf8")

    def toggle_aim_master(self):
        self.aim_enabled = bool(self.switch_aim.get())
        self._ensure_engine_running()
        if self.colorbot:
            self.colorbot.aim_enabled = self.aim_enabled

    def toggle_trigger_master(self):
        self.trigger_enabled = bool(self.switch_trigger.get())
        self._ensure_engine_running()
        if self.colorbot:
            self.colorbot.trigger_enabled = self.trigger_enabled

    def toggle_preview_stream(self):
        self.preview_enabled = bool(self.switch_preview.get())
        if self.preview_enabled:
            self._ensure_engine_running()

    def _ensure_engine_running(self):
        """Starts the engine if any feature (aimbot, triggerbot, or preview) needs it."""
        should_run = self.aim_enabled or self.trigger_enabled or self.preview_enabled
        if should_run:
            if not self.colorbot:
                try:
                    res_parts = self.resolution_input.get().split('x')
                    w, h = int(res_parts[0]), int(res_parts[1])
                except Exception:
                    w, h = 1920, 1080

                cx, cy = w // 2, h // 2
                grab_size = max(10, (int(self.fov) // 2) * 2)
                
                self.colorbot = Colorbot(
                    x=cx - grab_size // 2,
                    y=cy - grab_size // 2,
                    grabzone=grab_size,
                    color_name=self.shared_color,
                    aim_enabled=self.aim_enabled,
                    trigger_enabled=self.trigger_enabled,
                    aim_mode=self.aim_mode,
                    trigger_mode=self.trigger_mode,
                    aim_target=self.aim_target,
                    magnet_mode=self.magnet_mode,
                    burst_count=self.burst_count,
                    burst_delay=self.burst_delay,
                    sensitivity=self.sensitivity,
                    smoothing=self.smoothing,
                    head_offset=self.head_offset,
                    trigger_delay=self.trigger_delay,
                    capture_method=self.combobox_capture.get(),
                    mouse_method=self.combobox_mouse.get()
                )
                self.colorbot.start()
                self.status_label.configure(text="● Engine: Running", text_color="#22c55e")
            else:
                self.colorbot.aim_enabled = self.aim_enabled
                self.colorbot.trigger_enabled = self.trigger_enabled
                self.colorbot.aim_mode = self.aim_mode
                self.colorbot.trigger_mode = self.trigger_mode
                self.colorbot.aim_target = self.aim_target
                self.colorbot.magnet_mode = self.magnet_mode
                self.colorbot.color_name = self.shared_color
                self.colorbot.sensitivity = self.sensitivity
                self.colorbot.smoothing = self.smoothing
                self.colorbot.head_offset = self.head_offset
                self.colorbot.trigger_delay = self.trigger_delay / 1000.0
                self.status_label.configure(text="● Engine: Running", text_color="#22c55e")
        elif self.colorbot:
            self.colorbot.close()
            self.colorbot = None
            self.status_label.configure(text="● Engine: Standby", text_color="#71717a")

    def _listen_for_keys(self):
        """High-frequency background key listener for global master hotkeys & aim trigger keys."""
        master_hotkey_was_pressed = False
        aim_was_pressed = False
        trigger_was_pressed = False

        while self.listener_running:
            if not self.is_recording_key:
                try:
                    # 1. Global Master Hotkey (Toggles Master Aimbot Switch)
                    master_pressed = is_key_pressed(self.master_toggle_key)
                    if master_pressed and not master_hotkey_was_pressed:
                        self.after(0, self._on_master_hotkey_triggered)
                    master_hotkey_was_pressed = master_pressed

                    # 2. Aim Key Handling (Hold / Magnet / Toggle / Always)
                    aim_pressed = is_key_pressed(self.aim_key)
                    if self.colorbot:
                        self.colorbot.is_aim_key_pressed = aim_pressed
                        if self.aim_mode == "Toggle":
                            if aim_pressed and not aim_was_pressed:
                                self.colorbot.aim_toggled = not self.colorbot.aim_toggled
                        elif self.aim_mode == "Always":
                            self.colorbot.aim_toggled = True
                    aim_was_pressed = aim_pressed

                    # 3. Triggerbot Key Handling
                    trigger_pressed = is_key_pressed(self.trigger_key)
                    if self.colorbot:
                        self.colorbot.is_trigger_key_pressed = trigger_pressed
                        if self.trigger_mode == "Toggle":
                            if trigger_pressed and not trigger_was_pressed:
                                self.colorbot.trigger_toggled = not self.colorbot.trigger_toggled
                    trigger_was_pressed = trigger_pressed

                except Exception:
                    pass
            time.sleep(0.005)

    def _on_master_hotkey_triggered(self):
        """Called safely on main thread when master hotkey is pressed."""
        self.aim_enabled = not self.aim_enabled
        if self.aim_enabled:
            self.switch_aim.select()
        else:
            self.switch_aim.deselect()
        self.toggle_aim_master()

    def _update_preview_loop(self):
        """Renders live HUD preview at 30 FPS with real-time FPS, Latency, and dynamic FOV overlay."""
        try:
            if self.preview_enabled and self.colorbot:
                frame, mask, target, fps, latency_ms, is_aiming, is_triggering, gz = self.colorbot.get_preview_data()
                
                if frame is not None and frame.size > 0:
                    rendered = self._render_hud(frame, mask, target, fps, latency_ms, is_aiming, gz)
                    
                    # Scale to selected display dimension (e.g. 360x360, 400x400)
                    dim = getattr(self, 'preview_dim', 360)
                    resized = cv2.resize(rendered, (dim, dim), interpolation=cv2.INTER_NEAREST)
                    rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb_img)
                    
                    self.current_frame_img = ImageTk.PhotoImage(pil_img)
                    self.preview_label.configure(image=self.current_frame_img, text="")

                    # Update Popout Window if active
                    if self.popout_window is not None and self.popout_label is not None:
                        try:
                            self.popout_label.configure(image=self.current_frame_img, text="")
                        except Exception:
                            pass

                    # Update Telemetry Stats Bar
                    if target.get("found", False):
                        bone_name = target.get("bone", self.aim_target)
                        self.lbl_target_status.configure(text=f"Target: [ LOCKED ({bone_name}) ]", text_color="#22c55e")
                        self.lbl_target_delta.configure(
                            text=f"dX: {target['x_diff']:+d}px | dY: {target['y_diff']:+d}px (Dist: {target['dist']}px)"
                        )
                    else:
                        self.lbl_target_status.configure(text="Target: SEARCHING", text_color="#fbbf24")
                        self.lbl_target_delta.configure(text="dX: -- | dY: -- (Dist: --)")

                    # Color-code latency
                    lat_color = "#22c55e" if latency_ms < 1.0 else ("#eab308" if latency_ms < 3.0 else "#ef4444")
                    self.lbl_latency_stat.configure(text=f"⚡ {latency_ms:.2f} ms", text_color=lat_color)
                    self.lbl_fps_stat.configure(text=f"FPS: {fps:.0f}")
                    self.lbl_fov_live.configure(text=f"FOV: {gz}px")

                    # Update Sidebar Aim Status badge
                    if is_aiming:
                        self.aim_status_badge.configure(text="Aim: [ TRACKING ]", text_color="#38bdf8")
                    elif self.colorbot.is_aim_key_pressed:
                        if self.aim_mode == "Magnet":
                            self.aim_status_badge.configure(text="Aim: [ MAGNET ]", text_color="#06b6d4")
                        else:
                            self.aim_status_badge.configure(text="Aim: [ HELD ]", text_color="#a855f7")
                    else:
                        self.aim_status_badge.configure(text="Aim: IDLE", text_color="#a1a1aa")
                else:
                    self.preview_label.configure(image=None, text="[ Waiting for screen frames... ]")
            elif not self.colorbot:
                self.preview_label.configure(image=None, text="[ Engine Standby - Enable Aimbot or Stream ]")
                self.lbl_target_status.configure(text="Target: IDLE", text_color="#71717a")
                self.lbl_fps_stat.configure(text="FPS: 0")
                self.lbl_latency_stat.configure(text="⚡ 0.00 ms", text_color="#71717a")
        except Exception:
            pass

        # Schedule next preview frame (33ms = ~30 FPS)
        self.after(33, self._update_preview_loop)

    def _render_hud(self, frame, mask, target, fps, latency_ms, is_aiming, gz):
        """Draws HUD overlays, bounding boxes, crosshair, head marker, live FOV ring, and telemetry text."""
        gz_h, gz_w = frame.shape[:2]
        cx, cy = gz_w // 2, gz_h // 2

        # 1. Base display selection
        if self.preview_mode == "HSV Color Mask":
            if mask is not None:
                display = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            else:
                display = frame.copy()
        elif self.preview_mode == "Split View":
            if mask is not None:
                mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                display = np.hstack([frame.copy(), mask_bgr])
            else:
                display = frame.copy()
        else: # "Camera + HUD"
            display = frame.copy()

        # 2. Draw Crosshair (+) at Center
        crosshair_color = (0, 255, 255) if is_aiming else (0, 255, 0)
        cv2.line(display, (cx - 6, cy), (cx + 6, cy), crosshair_color, 1)
        cv2.line(display, (cx, cy - 6), (cx, cy + 6), crosshair_color, 1)

        # 3. Draw FOV Boundary Circle & Box (Real-time FOV visualization)
        fov_radius = max(4, gz // 2 - 1)
        cv2.circle(display, (cx, cy), fov_radius, (0, 255, 255), 1)
        cv2.rectangle(display, (0, 0), (gz_w - 1, gz_h - 1), (60, 60, 60), 1)

        # 4. Draw Detected Target Overlays
        if target.get("found", False):
            bx, by, bw, bh = target["x"], target["y"], target["w"], target["h"]
            tcX, target_y = target["cX"], target["target_y"]

            # Enemy Bounding Box (Green / Orange outline)
            box_color = (0, 255, 0) if not is_aiming else (0, 165, 255)
            cv2.rectangle(display, (bx, by), (bx + bw, by + bh), box_color, 1)

            # Target Lock Bone Point (Cyan Dot)
            cv2.circle(display, (tcX, target_y), 3, (255, 255, 0), -1)

            # Tracking Line from Crosshair to Target Point
            cv2.line(display, (cx, cy), (tcX, target_y), (255, 255, 0), 1)

        # 5. On-Screen Watermark / Telemetry HUD Text
        bone_tag = self.aim_target.upper()[:4]
        if self.aim_mode == "Magnet":
            mag_tag = "MAG-BURST" if "burst" in self.magnet_mode.lower() else "MAG-TAP"
        else:
            mag_tag = "AIM"
        info_text = f"{fps:.0f}FPS | {latency_ms:.2f}ms | FOV:{gz}px | {mag_tag}:{bone_tag}"
        cv2.putText(display, info_text, (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 255, 255), 1, cv2.LINE_AA)

        return display

    def toggle_popout_window(self):
        """Opens or closes a standalone resizable floating preview window."""
        if self.popout_window is None or not self.popout_window.winfo_exists():
            self.popout_window = customtkinter.CTkToplevel(self)
            self.popout_window.title("HUD Live Preview")
            self.popout_window.geometry("390x410")
            self.popout_window.attributes("-topmost", True)
            
            self.popout_label = customtkinter.CTkLabel(
                self.popout_window, text="[ Floating HD HUD Stream ]",
                font=customtkinter.CTkFont(size=12)
            )
            self.popout_label.pack(expand=True, fill="both", padx=10, pady=10)
        else:
            self.popout_window.focus()

    def change_key_text(self, key_target):
        """Records any pressed key or mouse button and updates the button label immediately."""
        if self.is_recording_key:
            return

        self.is_recording_key = True
        if key_target == "aim":
            target_btn = self.button_aim_key
        elif key_target == "master":
            target_btn = self.button_master_hotkey
        else:
            target_btn = self.button_trigger_key

        target_btn.configure(text="[Press Key...]", fg_color="#e67e22")

        def listener():
            recorded = record_key_or_mouse(timeout=8.0)
            if recorded:
                if key_target == "aim":
                    self.aim_key = recorded
                    self.button_aim_key.configure(text=f"{recorded}", fg_color=["#3a7ebf", "#1f538d"])
                elif key_target == "master":
                    self.master_toggle_key = recorded
                    self.button_master_hotkey.configure(text=f"Hotkey: {recorded.upper()}", fg_color=["#3a7ebf", "#1f538d"])
                else:
                    self.trigger_key = recorded
                    self.button_trigger_key.configure(text=f"{recorded}", fg_color=["#3a7ebf", "#1f538d"])
                self.save_config()
            else:
                if key_target == "aim":
                    target_btn.configure(text=f"{self.aim_key}", fg_color=["#3a7ebf", "#1f538d"])
                elif key_target == "master":
                    target_btn.configure(text=f"Hotkey: {self.master_toggle_key.upper()}", fg_color=["#3a7ebf", "#1f538d"])
                else:
                    target_btn.configure(text=f"{self.trigger_key}", fg_color=["#3a7ebf", "#1f538d"])
            self.is_recording_key = False

        Thread(target=listener, daemon=True).start()

    def aim_mode_callback(self, new_mode):
        self.aim_mode = new_mode
        if self.colorbot:
            self.colorbot.aim_mode = new_mode

    def magnet_fire_callback(self, new_fire_mode):
        self.magnet_mode = new_fire_mode
        if self.colorbot:
            self.colorbot.magnet_mode = new_fire_mode

    def aim_target_callback(self, new_target):
        self.aim_target = new_target
        if self.colorbot:
            self.colorbot.aim_target = new_target

    def trigger_mode_callback(self, new_mode):
        self.trigger_mode = new_mode
        if self.colorbot:
            self.colorbot.trigger_mode = new_mode

    def preview_mode_callback(self, new_mode):
        self.preview_mode = new_mode

    def color_change_callback(self, new_color):
        self.shared_color = new_color
        self.combobox_aim_color.set(new_color)
        self.combobox_trigger_color.set(new_color)
        if self.colorbot:
            self.colorbot.color_name = new_color

    def FOV_slider_callback(self, value):
        self.fov = max(10, (int(value) // 2) * 2)
        self.label_aim_FOV_value.configure(text=str(int(self.fov)))
        self.slider_preview_fov.set(self.fov)
        self.slider_aim_FOV.set(self.fov)
        self.lbl_fov_live.configure(text=f"FOV: {int(self.fov)}px")
        if self.colorbot:
            try:
                res_parts = self.resolution_input.get().split('x')
                w, h = int(res_parts[0]), int(res_parts[1])
            except Exception:
                w, h = 1920, 1080
            cx, cy = w // 2, h // 2
            self.colorbot.update_roi(cx, cy, self.fov)

    def sens_slider_callback(self, value):
        self.sensitivity = float(value)
        self.label_sens_value.configure(text=f"{self.sensitivity:.2f}")
        if self.colorbot:
            self.colorbot.sensitivity = self.sensitivity

    def smooth_slider_callback(self, value):
        self.smoothing = float(value)
        self.label_smooth_value.configure(text=f"{self.smoothing:.2f}")
        if self.colorbot:
            self.colorbot.smoothing = self.smoothing

    def head_slider_callback(self, value):
        self.head_offset = int(value)
        self.label_head_value.configure(text=str(self.head_offset))
        if self.colorbot:
            self.colorbot.head_offset = self.head_offset

    def delay_slider_callback(self, value):
        self.trigger_delay = float(value)
        self.label_trigger_delay_value.configure(text=str(int(value)))
        if self.colorbot:
            self.colorbot.trigger_delay = self.trigger_delay / 1000.0

    def load_config(self):
        self.config_manager.load_config()
        self._init_variables()
        
        # Update UI components
        if self.aim_enabled:
            self.switch_aim.select()
        else:
            self.switch_aim.deselect()
            
        if self.trigger_enabled:
            self.switch_trigger.select()
        else:
            self.switch_trigger.deselect()

        self.button_aim_key.configure(text=f"{self.aim_key}")
        self.button_master_hotkey.configure(text=f"Hotkey: {self.master_toggle_key.upper()}")
        self.combobox_aim_mode.set(self.aim_mode)
        self.combobox_magnet_fire.set(self.magnet_mode)
        self.combobox_aim_target.set(self.aim_target)
        self.button_trigger_key.configure(text=f"{self.trigger_key}")
        self.combobox_trigger_mode.set(self.trigger_mode)
        self.slider_aim_FOV.set(self.fov)
        self.slider_preview_fov.set(self.fov)
        self.label_aim_FOV_value.configure(text=str(int(self.fov)))
        self.lbl_fov_live.configure(text=f"FOV: {int(self.fov)}px")
        self.slider_sens.set(self.sensitivity)
        self.label_sens_value.configure(text=f"{self.sensitivity:.2f}")
        self.slider_smooth.set(self.smoothing)
        self.label_smooth_value.configure(text=f"{self.smoothing:.2f}")
        self.slider_head.set(self.head_offset)
        self.label_head_value.configure(text=str(self.head_offset))
        self.slider_trigger_delay.set(self.trigger_delay)
        self.label_trigger_delay_value.configure(text=str(int(self.trigger_delay)))
        self.combobox_capture.set(self.capture_method)
        self.combobox_mouse.set(self.mouse_method)
        self.combobox_aim_color.set(self.shared_color)
        self.combobox_trigger_color.set(self.shared_color)
        self.combobox_preview_size.set(self.preview_size_str)
        self.preview_size_callback(self.preview_size_str)
        self.resolution_input.delete(0, 'end')
        self.resolution_input.insert(0, self.formatted_resolution)
        self._ensure_engine_running()

    def save_config(self):
        res = self.resolution_input.get().split('x')
        config = {
            "MASTER_TOGGLE_KEY": self.master_toggle_key,
            "AIM_KEY": self.aim_key,
            "AIM_MODE": self.combobox_aim_mode.get(),
            "AIM_TARGET": self.combobox_aim_target.get(),
            "MAGNET_MODE": self.combobox_magnet_fire.get(),
            "BURST_COUNT": self.burst_count,
            "BURST_DELAY": self.burst_delay,
            "AIM_ENABLED": self.aim_enabled,
            "TRIGGER_KEY": self.trigger_key,
            "TRIGGER_MODE": self.combobox_trigger_mode.get(),
            "TRIGGER_ENABLED": self.trigger_enabled,
            "TRIGGER_DELAY": int(self.trigger_delay),
            "FOV": int(self.fov),
            "RESOLUTION": [res[0].strip(), res[1].strip()],
            "ENEMY_COLOR": self.shared_color,
            "SENSITIVITY": round(self.sensitivity, 2),
            "SMOOTHING": round(self.smoothing, 2),
            "HEAD_OFFSET": int(self.head_offset),
            "CAPTURE_METHOD": self.combobox_capture.get(),
            "MOUSE_METHOD": self.combobox_mouse.get(),
            "PREVIEW_MODE": self.combobox_preview_mode.get(),
            "PREVIEW_SIZE": self.combobox_preview_size.get()
        }
        self.config_manager.save_config(config)
        self.status_label.configure(text="● Config Saved!", text_color="#38bdf8")

    def destroy(self):
        self.listener_running = False
        if self.colorbot:
            self.colorbot.close()
            self.colorbot = None
        super().destroy()
