import queue
import time
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
        
        # Start background keyboard/mouse listener thread
        Thread(target=self.listen_for_keys, daemon=True).start()

    def _init_variables(self):
        self.aim_key = self.config_manager.get('TOGGLE_KEY', 'RMB')
        self.aim_mode = self.config_manager.get('AIM_MODE', 'Hold')
        self.trigger_key = self.config_manager.get('TRIGGER_KEY', 'f2')
        self.trigger_delay = float(self.config_manager.get('TRIGGER_DELAY', 25))
        self.fov = float(self.config_manager.get('FOV', 60))
        self.shared_color = self.config_manager.get('ENEMY_COLOR', 'Purple')
        self.resolution = self.config_manager.get('RESOLUTION', [1920, 1080])
        self.sensitivity = float(self.config_manager.get('SENSITIVITY', 0.35))
        self.smoothing = float(self.config_manager.get('SMOOTHING', 0.3))
        self.head_offset = int(self.config_manager.get('HEAD_OFFSET', 8))
        self.capture_method = self.config_manager.get('CAPTURE_METHOD', 'Auto')
        self.mouse_method = self.config_manager.get('MOUSE_METHOD', 'Auto')
        
        self.enabled_aim = False 
        self.enabled_trigger = False 
        self.formatted_resolution = f"{self.resolution[0]}x{self.resolution[1]}"
        self.is_recording_key = False
        self.colorbot = None

    def _setup_ui(self):
        self.resizable(False, False)
        self.title("Valorant Colorbot - 1PC & Keybinds")
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        self.geometry("820x360")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar_frame = customtkinter.CTkFrame(self, width=150, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=6, sticky="nsew")
        
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame, 
            text="Colorbot 1PC", 
            font=customtkinter.CTkFont(size=18, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=15, pady=(20, 15))

        self.sidebar_button_1 = customtkinter.CTkButton(
            self.sidebar_frame, text="Aimbot", 
            command=lambda: self.show_frame(self.aimbot_frame),
            font=customtkinter.CTkFont(size=14)
        )
        self.sidebar_button_1.grid(row=1, column=0, padx=15, pady=8)

        self.sidebar_button_2 = customtkinter.CTkButton(
            self.sidebar_frame, text="Triggerbot", 
            command=lambda: self.show_frame(self.triggerbot_frame),
            font=customtkinter.CTkFont(size=14)
        )
        self.sidebar_button_2.grid(row=2, column=0, padx=15, pady=8)

        self.sidebar_button_3 = customtkinter.CTkButton(
            self.sidebar_frame, text="Settings / Misc", 
            command=lambda: self.show_frame(self.misc_frame),
            font=customtkinter.CTkFont(size=14)
        )
        self.sidebar_button_3.grid(row=3, column=0, padx=15, pady=8)

        # Status Label
        self.status_label = customtkinter.CTkLabel(
            self.sidebar_frame, 
            text="Status: Ready", 
            text_color="#00ffcc",
            font=customtkinter.CTkFont(size=12)
        )
        self.status_label.grid(row=5, column=0, padx=10, pady=(40, 10))

        # Content Container
        self.content_frame = customtkinter.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, rowspan=6, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.aimbot_frame = customtkinter.CTkFrame(self.content_frame)
        self.triggerbot_frame = customtkinter.CTkFrame(self.content_frame)
        self.misc_frame = customtkinter.CTkFrame(self.content_frame)

        for frame in (self.aimbot_frame, self.triggerbot_frame, self.misc_frame):
            frame.grid(row=0, column=0, sticky="nsew")

        self._setup_aimbot_page()
        self._setup_triggerbot_page()
        self._setup_misc_page()
        
        self.show_frame(self.aimbot_frame)

    def _setup_aimbot_page(self):
        # Row 0: Switch, Key Button (records key/mouse), Aim Mode, Color
        self.switch_aim = customtkinter.CTkSwitch(
            self.aimbot_frame, text="Aimbot Active", 
            font=customtkinter.CTkFont(size=14, weight="bold"), 
            command=self.toggle_aim
        )
        self.switch_aim.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.button_aim_key = customtkinter.CTkButton(
            self.aimbot_frame, text=f"Key: {self.aim_key}", 
            command=lambda: self.change_key_text("aim"), 
            width=120, font=customtkinter.CTkFont(size=13)
        )
        self.button_aim_key.grid(row=0, column=1, padx=5, pady=10)

        self.combobox_aim_mode = customtkinter.CTkComboBox(
            self.aimbot_frame, values=["Hold", "Toggle"], 
            command=self.aim_mode_callback, width=90,
            font=customtkinter.CTkFont(size=13)
        )
        self.combobox_aim_mode.grid(row=0, column=2, padx=5, pady=10)
        self.combobox_aim_mode.set(self.aim_mode)

        self.combobox_aim_color = customtkinter.CTkComboBox(
            self.aimbot_frame, values=["Purple", "Yellow", "Red"], 
            command=self.color_change_callback, width=100,
            font=customtkinter.CTkFont(size=13)
        )
        self.combobox_aim_color.grid(row=0, column=3, padx=5, pady=10)
        self.combobox_aim_color.set(self.shared_color)

        # Row 1: FOV Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="FOV (Box Size):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.slider_aim_FOV = customtkinter.CTkSlider(self.aimbot_frame, from_=20, to=250, command=self.FOV_slider_callback)
        self.slider_aim_FOV.grid(row=1, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
        self.slider_aim_FOV.set(self.fov)
        self.label_aim_FOV_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.fov)))
        self.label_aim_FOV_value.grid(row=1, column=3, padx=5, pady=6)

        # Row 2: In-Game Sensitivity Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="Game Sensitivity:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.slider_sens = customtkinter.CTkSlider(self.aimbot_frame, from_=0.05, to=1.5, command=self.sens_slider_callback)
        self.slider_sens.grid(row=2, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
        self.slider_sens.set(self.sensitivity)
        self.label_sens_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=f"{self.sensitivity:.2f}")
        self.label_sens_value.grid(row=2, column=3, padx=5, pady=6)

        # Row 3: Smoothing Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="Smoothing Speed:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=3, column=0, padx=10, pady=6, sticky="w")
        self.slider_smooth = customtkinter.CTkSlider(self.aimbot_frame, from_=0.05, to=1.0, command=self.smooth_slider_callback)
        self.slider_smooth.grid(row=3, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
        self.slider_smooth.set(self.smoothing)
        self.label_smooth_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=f"{self.smoothing:.2f}")
        self.label_smooth_value.grid(row=3, column=3, padx=5, pady=6)

        # Row 4: Head Offset Slider
        customtkinter.CTkLabel(self.aimbot_frame, text="Head Y Offset:", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=4, column=0, padx=10, pady=6, sticky="w")
        self.slider_head = customtkinter.CTkSlider(self.aimbot_frame, from_=0, to=25, command=self.head_slider_callback)
        self.slider_head.grid(row=4, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
        self.slider_head.set(self.head_offset)
        self.label_head_value = customtkinter.CTkLabel(self.aimbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.head_offset)))
        self.label_head_value.grid(row=4, column=3, padx=5, pady=6)

    def _setup_triggerbot_page(self):
        # Row 0: Switch, Key Button, Color
        self.switch_trigger = customtkinter.CTkSwitch(
            self.triggerbot_frame, text="Triggerbot Active", 
            font=customtkinter.CTkFont(size=14, weight="bold"), 
            command=self.toggle_trigger
        )
        self.switch_trigger.grid(row=0, column=0, padx=10, pady=15, sticky="w")

        self.button_trigger_key = customtkinter.CTkButton(
            self.triggerbot_frame, text=f"Key: {self.trigger_key}", 
            command=lambda: self.change_key_text("trigger"), 
            width=120, font=customtkinter.CTkFont(size=13)
        )
        self.button_trigger_key.grid(row=0, column=1, padx=5, pady=15)

        self.combobox_trigger_color = customtkinter.CTkComboBox(
            self.triggerbot_frame, values=["Purple", "Yellow", "Red"], 
            command=self.color_change_callback, width=110,
            font=customtkinter.CTkFont(size=13)
        )
        self.combobox_trigger_color.grid(row=0, column=2, padx=5, pady=15)
        self.combobox_trigger_color.set(self.shared_color)

        # Row 1: Delay Slider
        customtkinter.CTkLabel(self.triggerbot_frame, text="Shot Delay (ms):", font=customtkinter.CTkFont(size=13, weight="bold")).grid(row=1, column=0, padx=10, pady=15, sticky="w")
        self.slider_trigger_delay = customtkinter.CTkSlider(self.triggerbot_frame, from_=0, to=200, command=self.delay_slider_callback)
        self.slider_trigger_delay.grid(row=1, column=1, padx=5, pady=15, sticky="ew")
        self.slider_trigger_delay.set(self.trigger_delay)
        self.label_trigger_delay_value = customtkinter.CTkLabel(self.triggerbot_frame, width=50, font=customtkinter.CTkFont(size=13), text=str(int(self.trigger_delay)))
        self.label_trigger_delay_value.grid(row=1, column=2, padx=5, pady=15)

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
            self.misc_frame, values=["Auto", "Win32", "Makcu"], 
            width=140, font=customtkinter.CTkFont(size=13)
        )
        self.combobox_mouse.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        self.combobox_mouse.set(self.mouse_method)

        # Row 3: Buttons
        btn_frame = customtkinter.CTkFrame(self.misc_frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=15)
        customtkinter.CTkButton(btn_frame, text="Load Config", command=self.load_config, width=120, font=customtkinter.CTkFont(size=13)).pack(side="left", padx=10)
        customtkinter.CTkButton(btn_frame, text="Save Config", command=self.save_config, width=120, font=customtkinter.CTkFont(size=13)).pack(side="left", padx=10)

    def toggle_aim(self):
        self.enabled_aim = self.switch_aim.get()
        self._update_colorbot()

    def toggle_trigger(self):
        self.enabled_trigger = self.switch_trigger.get()
        self._update_colorbot()

    def _update_colorbot(self):
        should_run = self.enabled_aim or self.enabled_trigger
        if should_run:
            if not self.colorbot:
                try:
                    res_parts = self.resolution_input.get().split('x')
                    w, h = int(res_parts[0]), int(res_parts[1])
                except Exception:
                    w, h = 1920, 1080

                cx, cy = w // 2, h // 2
                grab_size = int(self.fov)
                
                self.colorbot = Colorbot(
                    x=cx - grab_size // 2,
                    y=cy - grab_size // 2,
                    grabzone=grab_size,
                    color_name=self.shared_color,
                    aim_enabled=self.enabled_aim,
                    trigger_enabled=self.enabled_trigger,
                    sensitivity=self.sensitivity,
                    smoothing=self.smoothing,
                    head_offset=self.head_offset,
                    trigger_delay=self.trigger_delay,
                    capture_method=self.combobox_capture.get(),
                    mouse_method=self.combobox_mouse.get()
                )
                self.colorbot.start()
                self.status_label.configure(text="Status: Active", text_color="#00ff66")
            else:
                self.colorbot.aim_enabled = self.enabled_aim
                self.colorbot.trigger_enabled = self.enabled_trigger
                self.colorbot.sensitivity = self.sensitivity
                self.colorbot.smoothing = self.smoothing
                self.colorbot.head_offset = self.head_offset
                self.colorbot.color_name = self.shared_color
                self.colorbot.trigger_delay = self.trigger_delay / 1000.0
                self.status_label.configure(text="Status: Active", text_color="#00ff66")
        elif self.colorbot:
            self.colorbot.close()
            self.colorbot = None
            self.status_label.configure(text="Status: Standby", text_color="#aaaaaa")

    def show_frame(self, frame):
        frame.tkraise()

    def listen_for_keys(self):
        """Keyboard/Mouse listener handling both Hold and Toggle modes."""
        aim_was_pressed = False
        trigger_was_pressed = False

        while True:
            if not self.is_recording_key:
                try:
                    # 1. Aim Key Handling
                    aim_is_pressed = is_key_pressed(self.aim_key)
                    if self.aim_mode == "Hold":
                        if aim_is_pressed and not self.enabled_aim:
                            self.enabled_aim = True
                            self.switch_aim.select()
                            self._update_colorbot()
                        elif not aim_is_pressed and self.enabled_aim:
                            self.enabled_aim = False
                            self.switch_aim.deselect()
                            self._update_colorbot()
                    else: # Toggle Mode
                        if aim_is_pressed and not aim_was_pressed:
                            self.switch_aim.toggle()
                            self.toggle_aim()
                        aim_was_pressed = aim_is_pressed

                    # 2. Trigger Key Handling (Toggle)
                    trigger_is_pressed = is_key_pressed(self.trigger_key)
                    if trigger_is_pressed and not trigger_was_pressed:
                        self.switch_trigger.toggle()
                        self.toggle_trigger()
                    trigger_was_pressed = trigger_is_pressed

                except Exception:
                    pass
            time.sleep(0.01)

    def change_key_text(self, key_target):
        """Records any pressed key or mouse button and updates the button label immediately."""
        if self.is_recording_key:
            return

        self.is_recording_key = True
        target_btn = self.button_aim_key if key_target == "aim" else self.button_trigger_key
        target_btn.configure(text="[Press Any Key/Mouse...]", fg_color="#e67e22")

        def listener():
            recorded = record_key_or_mouse(timeout=8.0)
            if recorded:
                if key_target == "aim":
                    self.aim_key = recorded
                    self.button_aim_key.configure(text=f"Key: {recorded}", fg_color=["#3a7ebf", "#1f538d"])
                else:
                    self.trigger_key = recorded
                    self.button_trigger_key.configure(text=f"Key: {recorded}", fg_color=["#3a7ebf", "#1f538d"])
                self.save_config()
            else:
                current = self.aim_key if key_target == "aim" else self.trigger_key
                target_btn.configure(text=f"Key: {current}", fg_color=["#3a7ebf", "#1f538d"])
            self.is_recording_key = False

        Thread(target=listener, daemon=True).start()

    def aim_mode_callback(self, new_mode):
        self.aim_mode = new_mode

    def color_change_callback(self, new_color):
        self.shared_color = new_color
        self.combobox_aim_color.set(new_color)
        self.combobox_trigger_color.set(new_color)
        if self.colorbot:
            self.colorbot.color_name = new_color

    def FOV_slider_callback(self, value):
        self.fov = value
        self.label_aim_FOV_value.configure(text=str(int(value)))
        if self.colorbot:
            try:
                res_parts = self.resolution_input.get().split('x')
                w, h = int(res_parts[0]), int(res_parts[1])
            except Exception:
                w, h = 1920, 1080
            cx, cy = w // 2, h // 2
            grab_size = int(self.fov)
            self.colorbot.grabzone = grab_size
            self.colorbot.grabber.update_roi(cx - grab_size // 2, cy - grab_size // 2, grab_size)

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
        self.switch_aim.deselect()
        self.switch_trigger.deselect()
        
        # Update UI components
        self.button_aim_key.configure(text=f"Key: {self.aim_key}")
        self.combobox_aim_mode.set(self.aim_mode)
        self.button_trigger_key.configure(text=f"Key: {self.trigger_key}")
        self.slider_aim_FOV.set(self.fov)
        self.label_aim_FOV_value.configure(text=str(int(self.fov)))
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
        self.resolution_input.delete(0, 'end')
        self.resolution_input.insert(0, self.formatted_resolution)

    def save_config(self):
        res = self.resolution_input.get().split('x')
        config = {
            "TOGGLE_KEY": self.aim_key,
            "AIM_MODE": self.combobox_aim_mode.get(),
            "TRIGGER_KEY": self.trigger_key,
            "TRIGGER_DELAY": int(self.trigger_delay),
            "FOV": int(self.fov),
            "RESOLUTION": [res[0].strip(), res[1].strip()],
            "ENEMY_COLOR": self.shared_color,
            "SENSITIVITY": round(self.sensitivity, 2),
            "SMOOTHING": round(self.smoothing, 2),
            "HEAD_OFFSET": int(self.head_offset),
            "CAPTURE_METHOD": self.combobox_capture.get(),
            "MOUSE_METHOD": self.combobox_mouse.get()
        }
        self.config_manager.save_config(config)
        self.status_label.configure(text="Config Saved!", text_color="#00ff66")
