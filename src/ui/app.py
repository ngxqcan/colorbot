import queue
import time
import keyboard
import customtkinter
from threading import Thread
from core.colorbot import Colorbot
from utils.config_manager import ConfigManager

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("green")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()  

        self.config_manager = ConfigManager()
        self._init_variables()
        self._setup_ui()
        
        # Start background threads
        Thread(target=self.listen_for_keys, daemon=True).start()

    def _init_variables(self):
        self.aim_key = self.config_manager.get('TOGGLE_KEY', 'f1')
        self.trigger_key = self.config_manager.get('TRIGGER_KEY', 'f2')
        self.trigger_delay = self.config_manager.get('TRIGGER_DELAY', 100)
        self.fov = self.config_manager.get('FOV', 100)
        self.shared_color = self.config_manager.get('ENEMY_COLOR', 'Purple')
        self.resolution = self.config_manager.get('RESOLUTION', [1920, 1080])
        
        self.enabled = False 
        self.enabled_trigger = False 
        self.formatted_resolution = 'x'.join(map(str, self.resolution))
        self.key_queue = queue.Queue()
        self.current_key_target = None 
        self.colorbot = None

    def _setup_ui(self):
        self.resizable(False, False)
        self.title("github.com/Violevo")
        self.iconbitmap("icon.ico")
        self.geometry("750x220")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=6, sticky="nsew")
        
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame, 
            text="Coloraim v1.1", 
            font=customtkinter.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_button_1 = customtkinter.CTkButton(self.sidebar_frame, text="Aimbot", command=lambda: self.show_frame(self.aimbot_frame))
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        self.sidebar_button_2 = customtkinter.CTkButton(self.sidebar_frame, text="Triggerbot", command=lambda: self.show_frame(self.triggerbot_frame))
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)

        self.sidebar_button_3 = customtkinter.CTkButton(self.sidebar_frame, text="Misc", command=lambda: self.show_frame(self.misc_frame))
        self.sidebar_button_3.grid(row=3, column=0, padx=20, pady=10)

        # Content Frames
        self.content_frame = customtkinter.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, rowspan=6, sticky="nsew")

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
        self.switch_aim = customtkinter.CTkSwitch(self.aimbot_frame, text="Enabled", font=customtkinter.CTkFont(size=20, weight="bold"), command=self.toggle_aim)
        self.switch_aim.grid(row=0, column=0, padx=20, pady=20)

        self.button_aim_key = customtkinter.CTkButton(self.aimbot_frame, text=f"Key: {self.aim_key}", command=lambda: self.change_key_text("aim"), font=customtkinter.CTkFont(size=20))
        self.button_aim_key.grid(row=0, column=1, padx=10, pady=20)

        self.combobox_aim_color = customtkinter.CTkComboBox(self.aimbot_frame, values=["Purple", "Red", "Yellow"], command=self.color_change_callback, font=customtkinter.CTkFont(size=20))
        self.combobox_aim_color.grid(row=0, column=2, padx=10, pady=20)
        self.combobox_aim_color.set(self.shared_color)

        self.label_aim_FOV = customtkinter.CTkLabel(self.aimbot_frame, text="FOV", font=customtkinter.CTkFont(size=20, weight="bold"))
        self.label_aim_FOV.grid(row=1, column=0, padx=10, pady=20)

        self.slider_aim_FOV = customtkinter.CTkSlider(self.aimbot_frame, command=self.FOV_slider_callback, from_=10, to=500)
        self.slider_aim_FOV.grid(row=1, column=1, padx=0, pady=20)
        self.slider_aim_FOV.set(self.fov)

        self.label_aim_FOV_value = customtkinter.CTkLabel(self.aimbot_frame, width=80, font=customtkinter.CTkFont(size=20, weight="bold"), text=str(int(self.fov)))
        self.label_aim_FOV_value.grid(row=1, column=2, padx=0, pady=20)

    def _setup_triggerbot_page(self):
        self.switch_trigger = customtkinter.CTkSwitch(self.triggerbot_frame, text="Enabled", font=customtkinter.CTkFont(size=20, weight="bold"), command=self.toggle_trigger)
        self.switch_trigger.grid(row=0, column=0, padx=20, pady=20)

        self.button_trigger_key = customtkinter.CTkButton(self.triggerbot_frame, text=f"Key: {self.trigger_key}", command=lambda: self.change_key_text("trigger"), font=customtkinter.CTkFont(size=20))
        self.button_trigger_key.grid(row=0, column=1, padx=10, pady=20)

        self.combobox_trigger_color = customtkinter.CTkComboBox(self.triggerbot_frame, values=["Purple", "Red", "Yellow"], command=self.color_change_callback, font=customtkinter.CTkFont(size=20))
        self.combobox_trigger_color.grid(row=0, column=2, padx=10, pady=20)
        self.combobox_trigger_color.set(self.shared_color)

        self.label_trigger_delay = customtkinter.CTkLabel(self.triggerbot_frame, text="Delay (ms)", font=customtkinter.CTkFont(size=20, weight="bold"))
        self.label_trigger_delay.grid(row=1, column=0, padx=10, pady=20)

        self.slider_trigger_delay = customtkinter.CTkSlider(self.triggerbot_frame, command=self.delay_slider_callback, from_=0, to=500)
        self.slider_trigger_delay.grid(row=1, column=1, padx=0, pady=20)
        self.slider_trigger_delay.set(self.trigger_delay)

        self.label_trigger_delay_value = customtkinter.CTkLabel(self.triggerbot_frame, width=80, font=customtkinter.CTkFont(size=20, weight="bold"), text=str(int(self.trigger_delay)))
        self.label_trigger_delay_value.grid(row=1, column=2, padx=0, pady=20)

    def _setup_misc_page(self):
        customtkinter.CTkLabel(self.misc_frame, text="Resolution: ", font=customtkinter.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20)
        self.resolution_input = customtkinter.CTkEntry(self.misc_frame, font=customtkinter.CTkFont(size=20))
        self.resolution_input.grid(row=0, column=1, padx=10, pady=20)
        self.resolution_input.insert(0, self.formatted_resolution)

        customtkinter.CTkButton(self.misc_frame, text="Load Config", command=self.load_config, font=customtkinter.CTkFont(size=20)).grid(row=1, column=0, padx=20, pady=20)
        customtkinter.CTkButton(self.misc_frame, text="Save Config", command=self.save_config, font=customtkinter.CTkFont(size=20)).grid(row=1, column=1, padx=20, pady=20)

    def toggle_aim(self):
        self.enabled = self.switch_aim.get()
        self._update_colorbot()

    def toggle_trigger(self):
        self.enabled_trigger = self.switch_trigger.get()
        self._update_colorbot()

    def _update_colorbot(self):
        if self.enabled or self.enabled_trigger:
            if not self.colorbot:
                cx, cy = int(self.resolution[0]) // 2, int(self.resolution[1]) // 2
                self.colorbot = Colorbot(cx - int(self.fov) // 2, cy - int(self.fov) // 2, int(self.fov), self.shared_color, self.enabled, self.enabled_trigger)
                self.colorbot.start()
            else:
                self.colorbot.aim_enabled = self.enabled
                self.colorbot.trigger_enabled = self.enabled_trigger
        elif self.colorbot:
            self.colorbot.close()
            self.colorbot = None

    def show_frame(self, frame):
        frame.tkraise()

    def listen_for_keys(self):
        while True:
            if keyboard.is_pressed(self.aim_key):
                self.switch_aim.toggle()
                self.toggle_aim()
                time.sleep(0.3)
            if keyboard.is_pressed(self.trigger_key):
                self.switch_trigger.toggle()
                self.toggle_trigger()
                time.sleep(0.3)
            time.sleep(0.01)

    def change_key_text(self, key_target):
        self.current_key_target = key_target
        def listener():
            key = keyboard.read_key()
            if self.current_key_target == "aim":
                self.aim_key = key
                self.button_aim_key.configure(text=f"Key: {key}")
            else:
                self.trigger_key = key
                self.button_trigger_key.configure(text=f"Key: {key}")
            self.current_key_target = None
        Thread(target=listener, daemon=True).start()

    def color_change_callback(self, new_color):
        self.shared_color = new_color
        self.combobox_aim_color.set(new_color)
        self.combobox_trigger_color.set(new_color)

    def FOV_slider_callback(self, value):
        self.fov = value
        self.label_aim_FOV_value.configure(text=str(int(value)))

    def delay_slider_callback(self, value):
        self.trigger_delay = value
        self.label_trigger_delay_value.configure(text=str(int(value)))

    def load_config(self):
        self.config_manager.load_config()
        self._init_variables()
        self.switch_aim.deselect()
        self.switch_trigger.deselect()
        # Update UI elements
        self.button_aim_key.configure(text=f"Key: {self.aim_key}")
        self.button_trigger_key.configure(text=f"Key: {self.trigger_key}")
        self.slider_aim_FOV.set(self.fov)
        self.label_aim_FOV_value.configure(text=str(int(self.fov)))
        self.slider_trigger_delay.set(self.trigger_delay)
        self.label_trigger_delay_value.configure(text=str(int(self.trigger_delay)))
        self.resolution_input.delete(0, 'end')
        self.resolution_input.insert(0, self.formatted_resolution)

    def save_config(self):
        res = self.resolution_input.get().split('x')
        config = {
            "TOGGLE_KEY": self.aim_key,
            "TRIGGER_KEY": self.trigger_key,
            "TRIGGER_DELAY": int(self.trigger_delay),
            "FOV": int(self.fov),
            "RESOLUTION": [int(res[0]), int(res[1])],
            "ENEMY_COLOR": self.shared_color
        }
        self.config_manager.save_config(config)
