# Valorant Colorbot (1-PC & 2-PC Optimized)

A high-performance colorbot for Valorant optimized for **1-PC standalone setups** (ultra-low latency screen capture and direct kernel/hardware mouse control), while still retaining full compatibility with **2-PC setups** (NDI stream + MAKCU hardware controller).

---

## ⚡ Key Features & Optimizations

- **Magnet Mode (Aimbot + Triggerbot Combo)**:
  - Hold a single key to smoothly lock onto enemies and automatically fire as soon as your crosshair aligns with the target.
- **Target Bone Selection (Head / Neck / Body / Auto)**:
  - Configure target location to **Head** (head level), **Neck**, **Body / Chest** (center mass), or **Auto** (closest bone to crosshair).
- **Anti-Jitter Humanized Aim Smoothing**:
  - Sub-pixel delta accumulator and velocity clamping to prevent violent snapping, micro-jitter, and overshooting.
- **1-Click Legit & Magnet Presets**:
  - `[ 🎯 Legit ]`: FOV: 45, Smoothing: 0.18, Head Target (ultra-natural human assist).
  - `[ 🧲 Magnet ]`: FOV: 45, Smoothing: 0.20, Head Target + Auto-Fire.
  - `[ ⚡ Rage ]`: FOV: 85, Smoothing: 0.45, Snap tracking.
- **Multi-Driver Screen Capture (DXCam / MSS / Win32 GDI / NDI)**:
  - 144Hz–240Hz+ sub-millisecond screen capture (<0.5ms latency) centered on crosshair ROI.
- **Multi-Driver Mouse Emulation (Logitech G HUB / Makcu / Win32)**:
  - Kernel-level mouse emulation via Logitech G HUB driver / Makcu USB device to bypass user-mode synthetic input filtering.
- **Real-Time 256x256 Live HUD Preview**:
  - Live preview canvas with on-screen microsecond latency (`ms`) and FPS tracking.
  - Standalone popout floating HUD window.

---

## 🛠️ Installation & Setup (1-PC)

### 1. Requirements:
- Windows 10 / 11
- Python 3.10+

### 2. Setup Virtual Environment:
```bash
git clone https://github.com/ngxqcan/colorbot.git
cd colorbot
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
- **Preset Buttons**: `🎯 Legit`, `🧲 Magnet`, `⚡ Rage` for instant tuning.
- **Aim Key**: Key to hold or press for aim assist (e.g. `RMB`, `Mouse4`, `Mouse5`, `Alt`, `Shift`, `C`).
- **Aim Mode**:
  - `Hold`: Smooth tracking while Aim Key is held down.
  - `Magnet`: Smooth tracking + automatic firing when crosshair is on target.
  - `Toggle`: Pressing Aim Key toggles active tracking.
  - `Always`: Continuously tracks enemies inside FOV.
- **Target Bone**:
  - `Head`: Locks onto head level (upper contour + Head Offset).
  - `Neck`: Targets the neck area.
  - `Body`: Targets the torso/chest center.
  - `Auto`: Dynamically picks the bone closest to the crosshair.
- **Enemy Color**: `Purple` (default enemy highlight), `Yellow` (Deuteranopia), or `Red`.
- **FOV**: Bounding box size centered on crosshair (40–60 px recommended for legit play).
- **Game Sensitivity**: Match your exact in-game Valorant sensitivity (e.g. `0.35`).
- **Smoothing Factor**: Factor from 0.05 (ultra-smooth/humanized) to 1.0 (instant snap). Default `0.18` for legit.
- **Head Y-Offset**: Pixels from contour top to head center (default `7`–`8`).

### Triggerbot Settings:
- **Triggerbot Master Enable**: Main switch to enable triggerbot.
- **Trigger Key**: Keybind to trigger/toggle triggerbot (`F2`, `Mouse5`, etc.).
- **Shot Delay**: Delay in milliseconds before firing (default `30ms`).

### Live Preview Tab:
- **Stream Live**: Toggle real-time 256x256 preview canvas ON/OFF.
- **View Mode**: Switch between `Camera + HUD`, `HSV Color Mask`, and `Split View`.
- **Popout Window**: Opens a floating 256x256 HUD window for dual-monitor setups.

---

## 📜 License
This project is licensed under the GNU GPLv3 License.
