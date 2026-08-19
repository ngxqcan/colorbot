# Valorant Colorbot (1-PC & 2-PC Optimized)

A high-performance colorbot for Valorant optimized for **1-PC standalone setups** (ultra-low latency screen capture and direct mouse control), while still retaining full compatibility with **2-PC setups** (NDI stream + MAKCU hardware controller).

---

## ⚡ Key 1-PC Optimizations

- **Direct Screen Capture (DXCam / MSS / Win32 GDI)**:
  - Captures only the FOV region of interest (ROI) around the crosshair instead of the full screen.
  - Sub-millisecond latency (<0.5ms) and 144Hz–240Hz+ capture rate via DirectX Desktop Duplication API (DXCam).
  - No need for OBS, NDI streams, or second computers!
- **Direct 1-PC Mouse Emulation**:
  - Native Windows Input API via `ctypes` (`mouse_event` / `SendInput`).
  - Seamless automatic fallback to Makcu if a hardware USB device is connected.
- **In-Game Sensitivity Scaling**:
  - Accurate pixel-to-angle conversion:
    $$ \text{Movement Multiplier} = 1.07437623 \times \text{Sensitivity}^{-0.9936827126} $$
- **Humanized Smoothing & Head Offset**:
  - Adjustable smoothing factor for natural cursor tracking.
  - Configurable Head Y-Offset to lock onto head level rather than center of mass.
- **Hold & Toggle Aim Modes with 0ms Lag**:
  - Support for `Hold` mode (active only while key is held down), `Toggle` mode, and `Always` mode.
  - Independent Global Master Hotkey (e.g. `F1`) to toggle the bot without tabbing out.
- **Real-Time Live HUD Preview**:
  - Live 30–60 FPS video stream of captured FOV directly inside the UI or via floating Popout Window.
  - **Camera + HUD Mode**: Displays center crosshair (+), FOV bounds, enemy bounding box, and cyan head-aim dot.
  - **HSV Color Mask Mode**: Real-time binary mask to easily calibrate Purple/Yellow/Red enemy colors.
  - **Split View Mode**: Side-by-side Camera & Mask view.
  - **Live Telemetry**: Real-time FPS, Target Lock status (`[ LOCKED ]`), distance calculations, and key state.

---

## 🛠️ Installation & Setup (1-PC)

### 1. Requirements:
- Windows 10 / 11
- Python 3.10+

### 2. Setup Virtual Environment:
```bash
git clone https://github.com/Violevo/2PC-Valorant-Colorbot
cd 2PC-Valorant-Colorbot
python -m venv .venv
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies:
```bash
pip install -r requirements.txt
```

### 4. Run the Application:
```bash
python main.py
```

---

## ⚙️ Configuration Guide

### Aimbot Settings:
- **Aimbot Master Enable**: Main switch to activate the Aimbot engine.
- **Master Hotkey**: Global hotkey (`F1`) to toggle Aimbot ON/OFF from in-game.
- **Aim Key**: Key to hold or press for aim assistance (e.g. `RMB`, `Mouse4`, `Mouse5`, `Alt`, `Shift`, `C`).
- **Aim Mode**:
  - `Hold`: Locks/tracks enemies only while Aim Key is held down.
  - `Toggle`: Pressing Aim Key toggles active tracking.
  - `Always`: Continuously tracks enemies inside FOV.
- **Enemy Color**: `Purple` (default enemy highlight), `Yellow` (Deuteranopia), or `Red`.
- **FOV**: Bounding box size centered on crosshair (40–100 px recommended).
- **Game Sensitivity**: Match your exact in-game Valorant sensitivity (e.g. `0.35`).
- **Smoothing Factor**: Factor from 0.05 (slow/smooth) to 1.0 (instant snap).
- **Head Y-Offset**: Pixels above torso center to target head level (default `8`–`12`).

### Triggerbot Settings:
- **Triggerbot Master Enable**: Main switch to enable triggerbot.
- **Trigger Key**: Keybind to trigger/toggle triggerbot (`F2`, `Mouse5`, etc.).
- **Shot Delay**: Delay in milliseconds before firing (default `25ms`).

### Live Preview Tab:
- **Stream Live**: Toggle real-time preview canvas ON/OFF.
- **View Mode**: Switch between `Camera + HUD`, `HSV Color Mask`, and `Split View`.
- **Zoom Level**: Magnify small FOVs (`1x`, `1.5x`, `2x`, `3x`).
- **Popout Window**: Opens a floating HUD window for dual-monitor setups.

### Driver Settings (Settings tab):
- **Capture Driver**: `Auto` (detects fastest DXCam/MSS), `DXCam`, `MSS`, `GDI`, `NDI`.
- **Mouse Driver**: `Auto`, `Win32` (1-PC Direct API), `Makcu` (Hardware device).

---

## 📁 Project Structure

```text
├── main.py             # Entry point (root)
├── config.json         # Configuration settings
├── icon.ico            # UI Icon
├── requirements.txt    # Python dependencies
└── src/
    ├── main.py         # Main execution logic
    ├── core/
    │   └── colorbot.py # Detection, math scaling, aim loop & preview data
    ├── drivers/
    │   ├── mouse.py    # 1-PC Win32 API & Makcu hardware driver
    │   └── screen.py   # DXCam, MSS, GDI & NDI multi-driver capture
    ├── ui/
    │   └── app.py      # CustomTkinter UI with Live Preview & HUD controls
    └── utils/
        ├── config_manager.py # JSON configuration manager
        └── input_handler.py  # Global key listener & VK mappings
```

---

## 📜 License
This project is licensed under the GNU GPLv3 License.
