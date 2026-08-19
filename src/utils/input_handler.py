import sys
import time

try:
    import keyboard
except ImportError:
    keyboard = None

# Windows Virtual Key Codes mapping
VK_MAPPING = {
    # Mouse buttons
    "lmb": 0x01,
    "left_click": 0x01,
    "left click": 0x01,
    "rmb": 0x02,
    "right_click": 0x02,
    "right click": 0x02,
    "mmb": 0x04,
    "middle_click": 0x04,
    "middle click": 0x04,
    "mouse4": 0x05,
    "mouse 4": 0x05,
    "xbutton1": 0x05,
    "side1": 0x05,
    "mouse5": 0x06,
    "mouse 5": 0x06,
    "xbutton2": 0x06,
    "side2": 0x06,
    
    # Modifier keys
    "shift": 0x10,
    "lshift": 0xA0,
    "rshift": 0xA1,
    "ctrl": 0x11,
    "lctrl": 0xA2,
    "rctrl": 0xA3,
    "alt": 0x12,
    "lalt": 0xA4,
    "ralt": 0xA5,
    "caps lock": 0x14,
    "capslock": 0x14,
    "space": 0x20,
    "spacebar": 0x20,
    "tab": 0x09,
    
    # Function keys
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B
}

# Reverse mapping for display names from VK
MOUSE_VK_NAMES = {
    0x01: "LMB",
    0x02: "RMB",
    0x04: "MMB",
    0x05: "Mouse4",
    0x06: "Mouse5"
}

def is_key_pressed(key_name):
    """
    Checks whether the specified keyboard key or mouse button is currently held down.
    Supports:
      - Mouse: 'RMB', 'LMB', 'MMB', 'Mouse4', 'Mouse5', 'right_click', etc.
      - Keyboard: 'shift', 'alt', 'ctrl', 'f1', 'c', 'v', 'space', etc.
    """
    if not key_name:
        return False

    name_lower = str(key_name).strip().lower()

    # Check Windows API if on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            # Check if it's in known VK mapping (mouse or modifiers)
            if name_lower in VK_MAPPING:
                vk = VK_MAPPING[name_lower]
                return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0
            
            # Check single char key
            if len(name_lower) == 1 and name_lower.isalnum():
                vk = ctypes.windll.user32.VkKeyScanA(ord(name_lower[0])) & 0xFF
                if vk > 0:
                    return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0
        except Exception:
            pass

    # Fallback to keyboard library
    if keyboard is not None:
        try:
            return keyboard.is_pressed(name_lower)
        except Exception:
            return False

    return False

def record_key_or_mouse(timeout=10.0):
    """
    Waits for the user to press ANY keyboard key OR mouse button and returns its friendly name.
    Returns: string name of the key/button (e.g., 'RMB', 'Mouse4', 'Alt', 'Shift', 'F1', 'c', etc.)
    """
    is_windows = sys.platform == "win32"
    
    if is_windows:
        try:
            import ctypes
            user32 = ctypes.windll.user32

            # 1. Wait until Left Mouse Button and other buttons are released from clicking UI
            start_wait = time.time()
            while time.time() - start_wait < 1.0:
                lmb_state = user32.GetAsyncKeyState(0x01) & 0x8000
                rmb_state = user32.GetAsyncKeyState(0x02) & 0x8000
                if not lmb_state and not rmb_state:
                    break
                time.sleep(0.02)

            start_record = time.time()
            while time.time() - start_record < timeout:
                # Check mouse buttons first
                for vk, name in MOUSE_VK_NAMES.items():
                    if (user32.GetAsyncKeyState(vk) & 0x8000) != 0:
                        while (user32.GetAsyncKeyState(vk) & 0x8000) != 0:
                            time.sleep(0.01)
                        return name

                # Check common modifiers and keys via GetAsyncKeyState
                for name, vk in VK_MAPPING.items():
                    if vk not in MOUSE_VK_NAMES and (user32.GetAsyncKeyState(vk) & 0x8000) != 0:
                        while (user32.GetAsyncKeyState(vk) & 0x8000) != 0:
                            time.sleep(0.01)
                        return name.upper() if len(name) <= 3 else name.capitalize()

                # Check alphanumeric keys (A-Z, 0-9)
                for key_code in range(0x30, 0x5B):
                    if (user32.GetAsyncKeyState(key_code) & 0x8000) != 0:
                        while (user32.GetAsyncKeyState(key_code) & 0x8000) != 0:
                            time.sleep(0.01)
                        return chr(key_code).lower()

                time.sleep(0.01)
        except Exception:
            pass

    # Fallback using keyboard library if not windows or if loop timed out
    if keyboard is not None:
        try:
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                return event.name
        except Exception:
            pass

    return None
