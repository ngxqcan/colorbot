# Valorant Colorbot (1-PC & 2-PC Optimized)

A high-performance colorbot for Valorant optimized for **1-PC standalone setups** (ultra-low latency screen capture and direct kernel/hardware mouse control), while still retaining full compatibility with **2-PC setups** (NDI stream + MAKCU hardware controller).

---

## ⚡ Key Features & Optimizations

- **Magnet Mode with Tap & Burst Firing**:
  - `Tap`: Single precise bullet per trigger lock (ideal for Vandal/Sheriff/Guardian).
  - `Burst (2-Shot / 3-Shot)`: Fires a tight controlled burst with humanized shot cadence.
  - `Continuous`: Smooth tracking with full auto spray.
- **Large High-Definition Live Preview**:
  - Large **360x360 HD Canvas** (scalable to 400x400, 320x320, or 256x256).
  - **Live FOV Visualization**: Adjusting the FOV slider immediately expands/contracts the live yellow FOV ring and updates capture bounds in real-time.
  - Interactive FOV slider directly on the Preview toolbar.
- **Target Bone Selection (Head / Neck / Body / Auto)**:
  - Configure target location to **Head**, **Neck**, **Body / Chest**, or **Auto** (dynamic closest bone).
- **Anti-Jitter Humanized Aim Smoothing**:
  - Sub-pixel delta accumulator and velocity clamping to prevent violent snapping, micro-jitter, and overshooting.
- **1-Click Legit & Magnet Presets**:
  - `[ 🎯 Legit ]`: FOV: 45, Smoothing: 0.18, Head Target (ultra-natural human assist).
  - `[ 🧲 Mag Tap ]`: FOV: 45, Smoothing: 0.20, Head Target + Tap Fire.
  - `[ 💥 Mag Burst ]`: FOV: 45, Smoothing: 0.20, Head Target + 2-Shot Burst.
  - `[ ⚡ Rage ]`: FOV: 85, Smoothing: 0.45, Snap tracking.
- **Multi-Driver Screen Capture (DXCam / MSS / Win32 GDI / NDI)**:
  - 144Hz–240Hz+ sub-millisecond screen capture (<0.5ms latency) centered on crosshair ROI.
- **Multi-Driver Mouse Emulation (Logitech G HUB / Makcu / Win32)**:
  - Kernel-level mouse emulation via Logitech G HUB driver / Makcu USB device to bypass user-mode synthetic input filtering.

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
- **Preset Buttons**: `🎯 Legit`, `🧲 Mag Tap`, `💥 Mag Burst`, `⚡ Rage` for instant tuning.
- **Aim Key**: Key to hold or press for aim assist (e.g. `RMB`, `Mouse4`, `Mouse5`, `Alt`, `Shift`, `C`).
- **Aim Mode**:
  - `Hold`: Smooth tracking while Aim Key is held down.
  - `Magnet`: Smooth tracking + automatic firing (Tap or Burst).
  - `Toggle`: Pressing Aim Key toggles active tracking.
  - `Always`: Continuously tracks enemies inside FOV.
- **Magnet Fire**: `Tap`, `Burst (2-Shot)`, `Burst (3-Shot)`, `Continuous`.
- **Target Bone**: `Head`, `Neck`, `Body`, `Auto`.
- **FOV**: Bounding box size centered on crosshair (40–60 px recommended for legit play).
- **Game Sensitivity**: Match your exact in-game Valorant sensitivity (e.g. `0.35`).
- **Smoothing Factor**: Factor from 0.05 (ultra-smooth/humanized) to 1.0 (instant snap). Default `0.18` for legit.

### Live Preview Tab:
- **Stream Live**: Toggle real-time HD preview canvas ON/OFF.
- **View Mode**: `Camera + HUD`, `HSV Color Mask`, `Split View`.
- **Canvas Size**: `360x360` (Default), `400x400`, `320x320`, `256x256`.
- **Live FOV Slider**: Drag to see FOV box and yellow circle expand/shrink live.
- **Popout Window**: Standalone resizable floating HUD window.

---

## 📜 License
This project is licensed under the GNU GPLv3 License.
