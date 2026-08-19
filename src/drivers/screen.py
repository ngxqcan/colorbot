import sys
import time
import threading
import numpy as np

class ScreenCapture:
    """
    High-Performance Multi-Driver Screen Capture optimized for 1-PC (and 2-PC legacy).
    Supported methods:
      - 'auto'   : Auto-detect fastest available driver (DXCam -> MSS -> Win32 GDI).
      - 'dxcam'  : DirectX Desktop Duplication (GPU-to-CPU, <1ms latency, 144-240Hz+).
      - 'mss'    : Ultra-fast lightweight CPU screen grabber (cross-platform, low overhead).
      - 'gdi'    : Native Windows GDI BitBlt via ctypes (zero external dependencies).
      - 'ndi'    : Network Device Interface (Legacy 2-PC OBS-NDI stream).
    """
    def __init__(self, x=0, y=0, grabzone=100, method="auto"):
        self.x = int(x)
        self.y = int(y)
        self.grabzone = int(grabzone)
        self.method = method.lower() if method else "auto"
        
        self.screen = np.zeros((self.grabzone, self.grabzone, 3), dtype=np.uint8)
        self.lock = threading.Lock()
        self.running = True
        self.active_driver = None
        
        # Performance metrics
        self.frame_count = 0
        self.fps = 0.0
        self.start_time = time.time()

        # Driver handles
        self.dxcam_camera = None
        self.mss_instance = None
        self.ndi_recv = None

        self._init_driver()
        self._start_capture_thread()

    def _init_driver(self):
        """Initializes the selected or auto-detected capture backend."""
        is_windows = sys.platform == "win32"
        region = (self.x, self.y, self.x + self.grabzone, self.y + self.grabzone)

        # 1. Try DXCam (DirectX Desktop Duplication)
        if self.method in ("dxcam", "auto") and is_windows:
            try:
                import dxcam
                self.dxcam_camera = dxcam.create(device_idx=0, output_idx=0, output_color="BGR")
                if self.dxcam_camera:
                    self.dxcam_camera.start(region=region, target_fps=240)
                    self.active_driver = "dxcam"
                    print(f"[ScreenCapture] Initialized DXCam (DirectX Desktop Duplication) at ROI: {region}")
                    return
            except Exception as e:
                if self.method == "dxcam":
                    print(f"[Warning] DXCam initialization failed: {e}")

        # 2. Try MSS
        if self.method in ("mss", "auto"):
            try:
                import mss
                self.mss_instance = mss.mss()
                self.active_driver = "mss"
                print(f"[ScreenCapture] Initialized MSS Screen Grabber at ROI: {region}")
                return
            except Exception as e:
                if self.method == "mss":
                    print(f"[Warning] MSS initialization failed: {e}")

        # 3. Try Native Windows GDI (ctypes BitBlt)
        if self.method in ("gdi", "auto") and is_windows:
            self.active_driver = "gdi"
            print(f"[ScreenCapture] Initialized Native Win32 GDI Screen Capture at ROI: {region}")
            return

        # 4. Try NDI (Legacy 2-PC)
        if self.method == "ndi":
            try:
                from cyndilib.finder import Finder
                from cyndilib.receiver import Receiver
                finder = Finder()
                sources = finder.get_sources()
                if sources:
                    self.ndi_recv = Receiver(source_name=sources[0].name)
                    self.active_driver = "ndi"
                    print(f"[ScreenCapture] Initialized NDI Receiver: {sources[0].name}")
                    return
            except Exception as e:
                print(f"[Error] NDI initialization failed: {e}")

        # Fallback to MSS if nothing else
        try:
            import mss
            self.mss_instance = mss.mss()
            self.active_driver = "mss"
            print("[ScreenCapture] Fallback to MSS Screen Grabber.")
        except Exception:
            self.active_driver = "dummy"
            print("[ScreenCapture] Warning: No active capture driver available.")

    def update_roi(self, x, y, grabzone):
        """Dynamically updates the region of interest."""
        with self.lock:
            self.x = int(x)
            self.y = int(y)
            self.grabzone = int(grabzone)
            region = (self.x, self.y, self.x + self.grabzone, self.y + self.grabzone)

            if self.active_driver == "dxcam" and self.dxcam_camera:
                try:
                    self.dxcam_camera.stop()
                    self.dxcam_camera.start(region=region, target_fps=240)
                except Exception:
                    pass

    def _start_capture_thread(self):
        thread = threading.Thread(target=self._capture_loop, daemon=True)
        thread.start()

    def _capture_loop(self):
        """High-frequency capture loop optimized for sub-millisecond acquisition."""
        monitor = {"top": self.y, "left": self.x, "width": self.grabzone, "height": self.grabzone}

        while self.running:
            frame = None

            if self.active_driver == "dxcam" and self.dxcam_camera:
                frame = self.dxcam_camera.get_latest_frame()

            elif self.active_driver == "mss" and self.mss_instance:
                try:
                    monitor["top"] = self.y
                    monitor["left"] = self.x
                    monitor["width"] = self.grabzone
                    monitor["height"] = self.grabzone
                    sct_img = self.mss_instance.grab(monitor)
                    frame = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((self.grabzone, self.grabzone, 4))[:, :, :3]
                except Exception:
                    pass

            elif self.active_driver == "gdi":
                frame = self._grab_win32_gdi()

            elif self.active_driver == "ndi" and self.ndi_recv:
                ndi_frame = self.ndi_recv.get_video_frame()
                if ndi_frame is not None:
                    # Crop ROI from full NDI frame
                    full_img = np.array(ndi_frame.data)[:, :, :3]
                    h, w, _ = full_img.shape
                    y1 = max(0, min(self.y, h - self.grabzone))
                    x1 = max(0, min(self.x, w - self.grabzone))
                    frame = full_img[y1:y1 + self.grabzone, x1:x1 + self.grabzone]

            if frame is not None:
                with self.lock:
                    self.screen = frame
                self._update_fps()
            else:
                time.sleep(0.001)

    def _grab_win32_gdi(self):
        """Captures ROI using native Windows GDI (BitBlt) via ctypes."""
        if sys.platform != "win32":
            return None
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hwnd = 0
        h_src_dc = user32.GetDC(hwnd)
        h_mem_dc = gdi32.CreateCompatibleDC(h_src_dc)
        h_bitmap = gdi32.CreateCompatibleBitmap(h_src_dc, self.grabzone, self.grabzone)
        h_old_bitmap = gdi32.SelectObject(h_mem_dc, h_bitmap)

        # BitBlt from screen to memory DC
        SRCCOPY = 0x00CC0020
        gdi32.BitBlt(h_mem_dc, 0, 0, self.grabzone, self.grabzone, h_src_dc, self.x, self.y, SRCCOPY)

        # Extract bitmap bytes
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.grabzone
        bmi.bmiHeader.biHeight = -self.grabzone  # Top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        buffer_size = self.grabzone * self.grabzone * 4
        buf = (ctypes.c_char * buffer_size)()

        gdi32.GetDIBits(h_mem_dc, h_bitmap, 0, self.grabzone, ctypes.byref(buf), ctypes.byref(bmi), 0)

        # Clean up GDI objects
        gdi32.SelectObject(h_mem_dc, h_old_bitmap)
        gdi32.DeleteObject(h_bitmap)
        gdi32.DeleteDC(h_mem_dc)
        user32.ReleaseDC(hwnd, h_src_dc)

        img_arr = np.frombuffer(buf, dtype=np.uint8).reshape((self.grabzone, self.grabzone, 4))
        return img_arr[:, :, :3]

    def _update_fps(self):
        self.frame_count += 1
        elapsed = time.time() - self.start_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.start_time = time.time()

    def get_screen(self):
        """Returns the latest captured frame slice."""
        with self.lock:
            return self.screen.copy()

    def stop(self):
        """Stops the capture thread and releases driver handles."""
        self.running = False
        if self.dxcam_camera:
            try:
                self.dxcam_camera.stop()
            except Exception:
                pass
            self.dxcam_camera = None
        if self.mss_instance:
            try:
                self.mss_instance.close()
            except Exception:
                pass
            self.mss_instance = None
