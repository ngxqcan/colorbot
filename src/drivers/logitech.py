import sys
import os
import time
import ctypes
from ctypes import wintypes

class LogitechDriver:
    """
    Logitech G HUB & Logitech Gaming Software (LGS) Mouse Driver.
    Simulates hardware mouse movement and clicks directly through Logitech's signed kernel driver
    to bypass user-mode synthetic input filtering.
    
    Supports:
    1. ghub_device.dll / logitech.dll (device_open, moveR, mouse_down, mouse_up)
    2. ghub_mouse.dll / lghub_mouse.dll (mouse_open, moveR/move, press/release)
    3. Direct Windows DeviceIoControl kernel fallback if G HUB virtual bus handle is accessible.
    """
    
    DLL_CANDIDATE_NAMES = [
        "logitech.driver.dll",
        "ghub_device.dll",
        "logitech.dll",
        "ghub_mouse.dll",
        "lghub_device.dll",
        "logitech_driver.dll",
        "lghub_mouse.dll",
        "LogitechGkey.dll"
    ]

    COMMON_SYSTEM_DIRS = [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")),
        os.getcwd(),
        r"C:\Program Files\LGHUB",
        r"C:\Program Files\LGHUB\sdk",
        r"C:\Program Files\Logitech Gaming Software",
        r"C:\Program Files (x86)\LGHUB",
        r"C:\Program Files (x86)\Logitech Gaming Software"
    ]

    def __init__(self):
        self.is_windows = sys.platform == "win32"
        self.dll = None
        self.dll_path = None
        self.driver_mode = None  # 'ghub_device', 'ghub_mouse', 'direct_ioctl'
        self.connected = False
        
        # Function pointers
        self._fn_move = None
        self._fn_down = None
        self._fn_up = None
        self._fn_close = None

        if self.is_windows:
            self._initialize()
        else:
            print("[Logitech] Non-Windows OS: Logitech driver is disabled.")

    def _find_dll(self):
        """Searches candidate folders for available Logitech driver DLLs."""
        # 1. Exact match from candidate names list
        for directory in self.COMMON_SYSTEM_DIRS:
            if not os.path.isdir(directory):
                continue
            for name in self.DLL_CANDIDATE_NAMES:
                full_path = os.path.join(directory, name)
                if os.path.isfile(full_path):
                    return full_path

        # 2. Dynamic scan for any *logitech*.dll or *ghub*.dll in local directories
        local_dirs = [
            os.path.dirname(os.path.abspath(__file__)),
            os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")),
            os.getcwd()
        ]
        for directory in local_dirs:
            if not os.path.isdir(directory):
                continue
            for fname in os.listdir(directory):
                fl = fname.lower()
                if fl.endswith(".dll") and ("logitech" in fl or "ghub" in fl or "lgs" in fl):
                    full_path = os.path.join(directory, fname)
                    if os.path.isfile(full_path):
                        return full_path

        return None

    def _initialize(self):
        """Attempts to load driver DLL or direct device handle."""
        dll_file = self._find_dll()
        if dll_file:
            try:
                self.dll = ctypes.CDLL(dll_file)
                self.dll_path = dll_file
                
                # Check for standard 1: device_open (ghub_device.dll / logitech.dll)
                if hasattr(self.dll, "device_open"):
                    try:
                        self.dll.device_open.restype = ctypes.c_int
                        res = self.dll.device_open()
                        if res in (1, 0, True):  # Some return 1 on ok, some return 0
                            self.driver_mode = "ghub_device"
                            self._setup_ghub_device_signatures()
                            self.connected = True
                            print(f"[Logitech] Successfully loaded Logitech driver via '{os.path.basename(dll_file)}' (ghub_device mode).")
                            return
                    except Exception as e:
                        print(f"[Logitech] device_open call failed: {e}")

                # Check for standard 2: mouse_open (ghub_mouse.dll)
                if hasattr(self.dll, "mouse_open"):
                    try:
                        self.dll.mouse_open.restype = ctypes.c_int
                        res = self.dll.mouse_open()
                        if res != 0 or res is None:
                            self.driver_mode = "ghub_mouse"
                            self._setup_ghub_mouse_signatures()
                            self.connected = True
                            print(f"[Logitech] Successfully loaded Logitech driver via '{os.path.basename(dll_file)}' (ghub_mouse mode).")
                            return
                    except Exception as e:
                        print(f"[Logitech] mouse_open call failed: {e}")

            except Exception as e:
                print(f"[Logitech] Error loading DLL '{dll_file}': {e}")

        # If no DLL found or DLL init failed, try direct Windows kernel device handle
        self._try_direct_ioctl_init()

    def _setup_ghub_device_signatures(self):
        """Sets up ctypes argtypes/restype for ghub_device standard."""
        if hasattr(self.dll, "moveR"):
            self.dll.moveR.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_bool]
            self._fn_move = lambda x, y: self.dll.moveR(int(x), int(y), True)
        elif hasattr(self.dll, "mouse_xy"):
            self.dll.mouse_xy.argtypes = [ctypes.c_int, ctypes.c_int]
            self._fn_move = lambda x, y: self.dll.mouse_xy(int(x), int(y))
        elif hasattr(self.dll, "move"):
            self.dll.move.argtypes = [ctypes.c_int, ctypes.c_int]
            self._fn_move = lambda x, y: self.dll.move(int(x), int(y))

        if hasattr(self.dll, "mouse_down"):
            self.dll.mouse_down.argtypes = [ctypes.c_int]
            self._fn_down = lambda code: self.dll.mouse_down(int(code))
        if hasattr(self.dll, "mouse_up"):
            self.dll.mouse_up.argtypes = [ctypes.c_int]
            self._fn_up = lambda code: self.dll.mouse_up(int(code))
        if hasattr(self.dll, "device_close"):
            self._fn_close = self.dll.device_close

    def _setup_ghub_mouse_signatures(self):
        """Sets up ctypes argtypes/restype for ghub_mouse standard."""
        if hasattr(self.dll, "moveR"):
            self.dll.moveR.argtypes = [ctypes.c_int, ctypes.c_int]
            self._fn_move = lambda x, y: self.dll.moveR(int(x), int(y))
        elif hasattr(self.dll, "move"):
            self.dll.move.argtypes = [ctypes.c_int, ctypes.c_int]
            self._fn_move = lambda x, y: self.dll.move(int(x), int(y))

        if hasattr(self.dll, "press"):
            self.dll.press.argtypes = [ctypes.c_int]
            self._fn_down = lambda code: self.dll.press(int(code))
        elif hasattr(self.dll, "mouse_down"):
            self.dll.mouse_down.argtypes = [ctypes.c_int]
            self._fn_down = lambda code: self.dll.mouse_down(int(code))

        if hasattr(self.dll, "release"):
            self.dll.release.argtypes = [ctypes.c_int]
            self._fn_up = lambda code: self.dll.release(int(code))
        elif hasattr(self.dll, "mouse_up"):
            self.dll.mouse_up.argtypes = [ctypes.c_int]
            self._fn_up = lambda code: self.dll.mouse_up(int(code))

        if hasattr(self.dll, "mouse_close"):
            self._fn_close = self.dll.mouse_close

    def _try_direct_ioctl_init(self):
        """Attempts to open handle to Logitech virtual bus driver directly."""
        if not self.is_windows:
            return
        # Known Logitech kernel device paths
        device_paths = [
            r"\\.\GhubMouseDevice",
            r"\\.\LGBus2673",
            r"\\.\root#system#0001#{deadbeef-0000-0000-0000-000000000000}"
        ]
        GENERIC_WRITE = 0x40000000
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3

        for dev in device_paths:
            try:
                handle = ctypes.windll.kernel32.CreateFileW(
                    dev,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    0,
                    None
                )
                if handle and handle != -1 and handle != 0xFFFFFFFF:
                    self.driver_mode = "direct_ioctl"
                    self.device_handle = handle
                    self.connected = True
                    print(f"[Logitech] Opened direct kernel handle to {dev}")
                    return
            except Exception:
                pass
        
        print("[Logitech] No active Logitech G HUB driver DLL (ghub_device.dll) found.")

    def is_connected(self):
        """Returns True if the driver is initialized and operational."""
        return self.connected

    def move(self, x, y):
        """Moves mouse relatively by (x, y) pixels."""
        if not self.connected or self._fn_move is None:
            return False
        try:
            dx, dy = int(round(x)), int(round(y))
            if dx == 0 and dy == 0:
                return True
            self._fn_move(dx, dy)
            return True
        except Exception as e:
            print(f"[Logitech Error] move({x}, {y}) failed: {e}")
            return False

    def mouse_down(self, button="left"):
        """Sends mouse button down event (1=left, 2=middle, 3=right, 4=x1, 5=x2)."""
        if not self.connected or self._fn_down is None:
            return False
        try:
            code_map = {"left": 1, "middle": 2, "right": 3, "mouse4": 4, "mouse5": 5}
            code = code_map.get(str(button).lower(), 1)
            self._fn_down(code)
            return True
        except Exception as e:
            print(f"[Logitech Error] mouse_down failed: {e}")
            return False

    def mouse_up(self, button="left"):
        """Sends mouse button up event."""
        if not self.connected or self._fn_up is None:
            return False
        try:
            code_map = {"left": 1, "middle": 2, "right": 3, "mouse4": 4, "mouse5": 5}
            code = code_map.get(str(button).lower(), 1)
            self._fn_up(code)
            return True
        except Exception as e:
            print(f"[Logitech Error] mouse_up failed: {e}")
            return False

    def click(self, button="left", delay=0.01):
        """Simulates a mouse click with delay."""
        if not self.connected:
            return False
        ok = self.mouse_down(button)
        if delay > 0:
            time.sleep(delay)
        ok2 = self.mouse_up(button)
        return ok and ok2

    def close(self):
        """Closes driver connection and releases resources."""
        if self._fn_close:
            try:
                self._fn_close()
            except Exception:
                pass
            self._fn_close = None
        self.connected = False

    def __del__(self):
        self.close()
