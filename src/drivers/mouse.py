import sys
import os
import ctypes
import time
from drivers.logitech import LogitechDriver

# Win32 Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

class PicoMouse:
    """
    Unified Mouse Driver supporting:
    1. 'kmnet'    - Kmbox NET Hardware device (Network hardware mouse, 100% undetected).
    2. 'logitech' - Logitech G HUB / LGS signed driver (1-PC kernel mouse emulation, bypasses Vanguard user-mode blocks).
    3. 'makcu'    - Makcu / Pico USB hardware device for 2-PC or hardware-spoofed 1-PC setup.
    4. 'win32'    - Direct Windows API (mouse_event / ctypes) for standard desktop apps.
    5. 'auto'     - Tries Kmbox NET -> Makcu -> Logitech -> falls back to Win32.
    """
    def __init__(self, method="auto", kmnet_ip="192.168.2.188", kmnet_port=16896, kmnet_uuid="46405c53"):
        self.method = method.lower() if method else "auto"
        self.kmnet_ip = str(kmnet_ip)
        self.kmnet_port = int(kmnet_port) if kmnet_port else 16896
        self.kmnet_uuid = str(kmnet_uuid)
        
        self.kmnet_driver = None
        self.makcu_controller = None
        self.logitech_driver = None
        self.active_driver = "win32"
        self.is_windows = sys.platform == "win32"
        self.is_left_down = False

        self._init_driver()

    def _init_driver(self):
        # 1. Try Kmbox NET Hardware
        if self.method in ("kmnet", "auto"):
            try:
                module_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "module")
                if os.path.isdir(module_dir) and module_dir not in sys.path:
                    sys.path.insert(0, module_dir)
                import kmNet
                ret = kmNet.init(str(self.kmnet_ip), str(self.kmnet_port), str(self.kmnet_uuid))
                if ret == 0 or ret is None:
                    self.kmnet_driver = kmNet
                    self.active_driver = "kmnet"
                    print(f"[Mouse] Kmbox NET hardware connected to {self.kmnet_ip}:{self.kmnet_port}")
                    return
            except Exception as e:
                if self.method == "kmnet":
                    print(f"[Warning] Kmbox NET connection failed: {e}. Falling back...")
                self.kmnet_driver = None
            except Exception as e:
                if self.method == "makcu":
                    print(f"[Warning] Makcu connection failed: {e}. Falling back...")
                self.makcu_controller = None

        # 2. Try Logitech G HUB / LGS Driver
        if self.method in ("logitech", "ghub", "lgs", "auto"):
            try:
                self.logitech_driver = LogitechDriver()
                if self.logitech_driver.is_connected():
                    self.active_driver = "logitech"
                    print("[Mouse] Logitech G HUB driver initialized successfully.")
                    return
                elif self.method in ("logitech", "ghub", "lgs"):
                    print("[Warning] Logitech driver requested but ghub_device.dll / driver not found.")
            except Exception as e:
                print(f"[Warning] Logitech driver init error: {e}")
                self.logitech_driver = None

        # 3. Fallback to direct Windows API
        if self.is_windows:
            self.active_driver = "win32"
            print("[Mouse] Using 1-PC Direct Windows API (ctypes mouse_event). Note: blocked by Valorant Vanguard in-game.")
        else:
            self.active_driver = "stub"
            print("[Mouse] Non-Windows platform detected; using safe stub driver.")

    def move(self, x, y):
        """Moves the mouse relatively by (x, y) coordinates."""
        dx, dy = int(round(x)), int(round(y))
        if dx == 0 and dy == 0:
            return

        # Kmbox NET hardware
        if self.active_driver == "kmnet" and self.kmnet_driver:
            try:
                self.kmnet_driver.move(dx, dy)
                return
            except Exception as e:
                print(f"[Error] Kmbox NET move failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Makcu hardware
        if self.active_driver == "makcu" and self.makcu_controller:
            try:
                self.makcu_controller.move(dx, dy)
                return
            except Exception as e:
                print(f"[Error] Makcu move failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Logitech G HUB driver
        if self.active_driver == "logitech" and self.logitech_driver:
            if self.logitech_driver.move(dx, dy):
                return
            else:
                print("[Error] Logitech move failed; switching to win32 fallback.")
                self.active_driver = "win32"

        # Win32 user32.mouse_event
        if self.active_driver == "win32" and self.is_windows:
            try:
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)
            except Exception as e:
                print(f"[Error] Win32 mouse_event failed: {e}")

    def mouse_down(self, button="left"):
        """Holds down a mouse button (for burst spray and continuous fire)."""
        if button == "left":
            self.is_left_down = True

        # Kmbox NET hardware
        if self.active_driver == "kmnet" and self.kmnet_driver:
            try:
                if button == "left":
                    self.kmnet_driver.left(1)
                elif button == "right":
                    self.kmnet_driver.right(1)
                elif button == "middle":
                    self.kmnet_driver.middle(1)
                return
            except Exception as e:
                print(f"[Error] Kmbox NET press failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Makcu hardware
        if self.active_driver == "makcu" and self.makcu_controller:
            try:
                from makcu import MouseButton
                btn = MouseButton.LEFT if button == "left" else MouseButton.RIGHT
                self.makcu_controller.press(btn)
                return
            except Exception as e:
                print(f"[Error] Makcu press failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Logitech G HUB driver
        if self.active_driver == "logitech" and self.logitech_driver:
            if self.logitech_driver.mouse_down(button):
                return
            else:
                self.active_driver = "win32"

        # Win32 user32.mouse_event
        if self.active_driver == "win32" and self.is_windows:
            try:
                flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
                ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)
            except Exception as e:
                print(f"[Error] Win32 mouse_down failed: {e}")

    def mouse_up(self, button="left"):
        """Releases a held mouse button."""
        if button == "left":
            self.is_left_down = False

        # Kmbox NET hardware
        if self.active_driver == "kmnet" and self.kmnet_driver:
            try:
                if button == "left":
                    self.kmnet_driver.left(0)
                elif button == "right":
                    self.kmnet_driver.right(0)
                elif button == "middle":
                    self.kmnet_driver.middle(0)
                return
            except Exception as e:
                print(f"[Error] Kmbox NET release failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Makcu hardware
        if self.active_driver == "makcu" and self.makcu_controller:
            try:
                from makcu import MouseButton
                btn = MouseButton.LEFT if button == "left" else MouseButton.RIGHT
                self.makcu_controller.release(btn)
                return
            except Exception as e:
                print(f"[Error] Makcu release failed ({e}); switching to fallback.")
                self.active_driver = "win32"

        # Logitech G HUB driver
        if self.active_driver == "logitech" and self.logitech_driver:
            if self.logitech_driver.mouse_up(button):
                return
            else:
                self.active_driver = "win32"

        # Win32 user32.mouse_event
        if self.active_driver == "win32" and self.is_windows:
            try:
                flag = MOUSEEVENTF_LEFTUP if button == "left" else MOUSEEVENTF_RIGHTUP
                ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)
            except Exception as e:
                print(f"[Error] Win32 mouse_up failed: {e}")

    def press(self, button="left"):
        self.mouse_down(button)

    def release(self, button="left"):
        self.mouse_up(button)

    def click(self, button="left", delay=0.015):
        """Simulates a mouse click with a realistic press-release duration."""
        self.mouse_down(button)
        if delay > 0:
            time.sleep(delay)
        self.mouse_up(button)

    def close(self):
        """Releases any held buttons and cleans up driver resources."""
        if self.is_left_down:
            self.mouse_up("left")

        if self.makcu_controller:
            try:
                self.makcu_controller.disconnect()
            except Exception:
                pass
            self.makcu_controller = None

        if self.logitech_driver:
            try:
                self.logitech_driver.close()
            except Exception:
                pass
            self.logitech_driver = None

    def __del__(self):
        self.close()
