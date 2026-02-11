import threading
import time
import numpy as np
from PIL import Image
from cyndilib.finder import Finder
from cyndilib.receiver import Receiver

class ScreenCapture:  
    def __init__(self, x=0, y=0, grabzone=500):
        self.x, self.y, self.grabzone = x, y, grabzone
        self.screen = np.zeros((grabzone, grabzone, 3), np.uint8)
        self.pillow = None
        self.lock = threading.Lock()
        self.frame_count = 0
        self.start_time = time.time()
        self.running = True

        self.finder = Finder()
        source = self._select_ndi_source()
        
        if source:
            self.ndi_recv = Receiver(source_name=source.name)
            self._start_capture_thread()
        else:
            print("[Error] No NDI source selected. Capture will not start.")
            self.running = False

    def _select_ndi_source(self):
        """Finds and selects an NDI source from the network."""
        while True:
            print("\nSearching for NDI sources... (3s)")
            time.sleep(1)
            sources = self.finder.get_sources()

            if sources:
                print(f"Found {len(sources)} NDI source(s):")
                for i, src in enumerate(sources):
                    print(f"[{i}] {src.name}")

                user_input = input("Enter source number or press enter to restart: ").strip()

                if not user_input:
                    continue

                if user_input.isdigit():
                    index = int(user_input)
                    if 0 <= index < len(sources):
                        return sources[index]
                    else:
                        print("[Error] Invalid selection. Please enter a valid number.")
            else:
                retry = input("[Error] No NDI sources found. Press Enter to retry or 'q' to quit: ").strip().lower()
                if retry == 'q':
                    return None

    def _start_capture_thread(self):
        thread = threading.Thread(target=self._capture_ndi, daemon=True)
        thread.start()

    def _capture_ndi(self):
        while self.running:
            frame = self.ndi_recv.get_video_frame()
            if frame is not None:
                with self.lock:
                    # NDI frames are often RGBA, we take RGB
                    self.screen = np.array(frame.data)[:, :, :3]  
                self._update_fps()

    def _update_fps(self):
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= 1:
            fps = self.frame_count / elapsed_time
            print(f"FPS: {fps:.2f}", end="\r")
            self.frame_count = 0
            self.start_time = time.time()

    def get_screen(self):
        """Returns a copy of the current screen capture."""
        with self.lock:
            return self.screen.copy()

    def stop(self):
        """Stops the capture thread."""
        self.running = False
