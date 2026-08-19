import sys
import os
import ctypes
import time

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
    1. 'win32' - Direct Windows API (mouse_event / ctypes) for 1-PC single setup.
    2. 'makcu' - Makcu / Pico USB hardware device for 2-PC or hardware-spoofed 1-PC setup.
    3. 'auto'  - Tries Makcu first; falls back to win32 gracefully.
    """
    def __init__(self, method="auto"):
        self.method = method.lower() if method else "auto"
        self.makcu_controller = None
        self.active_driver = "win32"
        self.is_windows = sys.platform == "win32"

        self._init_driver()

    def _init_driver(self):
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
                    print(f"[Warning] Makcu connection failed: {e}. Falling back to Win32 API.")
                self.makcu_controller = None

        # Fallback to direct Windows API
        if self.is_windows:
            self.active_driver = "win32"
            print("[Mouse] Using 1-PC Direct Windows API (ctypes mouse_event).")
        else:
            self.active_driver = "stub"
            print("[Mouse] Non-Windows platform detected; using safe stub driver.")

    def move(self, x, y):
        """Moves the mouse relatively by (x, y) coordinates."""
        dx, dy = int(round(x)), int(round(y))
        if dx == 0 and dy == 0:
            return

        if self.active_driver == "makcu" and self.makcu_controller:
            try:
                self.makcu_controller.move(dx, dy)
                return
            except Exception as e:
                print(f"[Error] Makcu move failed ({e}); switching to Win32 API.")
                self.active_driver = "win32"

        if self.active_driver == "win32" and self.is_windows:
            try:
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)
            except Exception as e:
                print(f"[Error] Win32 mouse_event failed: {e}")

    def click(self, button="left", delay=0.01):
        """Simulates a mouse click with a realistic press-release duration."""
        if self.active_driver == "makcu" and self.makcu_controller:
            try:
                from makcu import MouseButton
                btn = MouseButton.LEFT if button == "left" else MouseButton.RIGHT
                self.makcu_controller.click(btn)
                return
            except Exception as e:
                print(f"[Error] Makcu click failed ({e}); switching to Win32 API.")
                self.active_driver = "win32"

        if self.active_driver == "win32" and self.is_windows:
            try:
                if button == "left":
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    if delay > 0:
                        time.sleep(delay)
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                elif button == "right":
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                    if delay > 0:
                        time.sleep(delay)
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            except Exception as e:
                print(f"[Error] Win32 click failed: {e}")

    def close(self):
        """Releases and cleans up driver resources."""
        if self.makcu_controller:
            try:
                self.makcu_controller.disconnect()
            except Exception:
                pass
            self.makcu_controller = None

    def __del__(self):
        self.close()
