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
    1. 'logitech' - Logitech G HUB / LGS signed driver (1-PC kernel mouse emulation, bypasses Vanguard user-mode blocks).
    2. 'makcu'    - Makcu / Pico USB hardware device for 2-PC or hardware-spoofed 1-PC setup.
    3. 'win32'    - Direct Windows API (mouse_event / ctypes) for standard desktop apps.
    4. 'auto'     - Tries Makcu first -> Logitech second -> falls back to Win32.
    """
    def __init__(self, method="auto"):
        self.method = method.lower() if method else "auto"
        self.makcu_controller = None
        self.logitech_driver = None
        self.active_driver = "win32"
        self.is_windows = sys.platform == "win32"
        self.is_left_down = False

        self._init_driver()

    def _init_driver(self):
        # 1. Try Makcu Hardware Device
        if self.method in ("makcu", "auto"):
            try:
                from makcu import create_controller
                self.makcu_controller = create_controller(debug=False, auto_reconnect=True)
                if not self.makcu_controller.is_connected():
                    self.makcu_controller.connect()
                if self.makcu_controller.is_connected():
                    self.active_driver = "makcu"
                    print("[Mouse] Makcu hardware controller connected successfully.")
                    return
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
