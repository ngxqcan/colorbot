# Valorant Colorbot (1-PC & 2-PC Optimized)

A high-performance colorbot for Valorant optimized for **1-PC standalone setups** (ultra-low latency screen capture and direct kernel/hardware mouse control), while still retaining full compatibility with **2-PC setups** (NDI stream + MAKCU hardware controller).

---

## ⚡ Key Features & Optimizations

- **Dedicated 🧲 Magnet Tab**:
  - Independent Magnet Master Enable, Keybind, and Target Bone selector.
  - **Customizable Firing Controls**:
    - **Burst Bullets Input Box & Slider**: Adjust number of bullets per burst (e.g. 1 to 6).
    - **Bullet Interval Delay (ms) Input & Slider**: Fine-tune shot cadence (40ms - 200ms).
    - **Recovery Cooldown (ms) Input & Slider**: Control pause between taps/bursts (80ms - 500ms).
  - 1-Click Weapon Presets: `[ 🎯 Vandal Tap ]`, `[ 💥 Phantom 2-Burst ]`, `[ ⚡ 3-Burst ]`.
- **Center-of-Head Targeting**:
  - Silhouette Bridging & Morphological Closing connects disconnected outline segments into a unified enemy character box.
  - Automatically aligns crosshair directly with the center of the skull / nose / eye level inside the character rather than the colored outline boundary.
- **Anti-Jitter Exponential Smoothing**:
  - Target coordinate low-pass EMA filter eliminates pixel jitter caused by game aliasing.
  - Smooth ease-in deceleration near target + sub-pixel float accumulator.
- **Large High-Definition Live Preview**:
  - Large **360x360 HD Canvas** (scalable to 400x400, 320x320, 256x256).
  - **Live FOV Ring**: Dynamic yellow circle shows exact FOV bounds in real time.
  - Quick FOV slider directly on Preview toolbar.
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

### 1. 🎯 Aimbot Tab:
- **Aimbot Master Enable**: Main switch for standard aim assist.
- **Aim Key**: Key to hold or toggle (`RMB`, `Mouse4`, `Mouse5`, `Alt`, etc.).
- **Aim Mode**: `Hold`, `Toggle`, `Always`.
- **Target Bone**: `Head`, `Neck`, `Body`, `Auto`.
- **Enemy Color**: `Purple` (Default), `Yellow`, `Red`.
- **FOV, Sensitivity, Smoothing, Head Offset**: Fully adjustable with sliders.

### 2. 🧲 Magnet Bot Tab (Dedicated):
- **Magnet Master Enable**: Activates Magnet auto-aim + auto-fire.
- **Magnet Key**: Independent keybind for Magnet mode.
- **Firing Mode**: `Tap`, `Burst`, `Continuous`.
- **Burst Bullets**: Direct number entry or slider (1–6 bullets).
- **Bullet Interval Delay (ms)**: Direct number entry or slider.
- **Shot Cooldown (ms)**: Direct number entry or slider.
- **Magnet FOV & Smoothing**: Dedicated sliders for Magnet mode.

### 3. ⚡ Triggerbot Tab:
- **Triggerbot Master Enable**: Main switch.
- **Trigger Key & Mode**: `Toggle`, `Hold`, `Always`.
- **Shot Delay (ms)**: Milliseconds before firing when crosshair is over enemy.

### 4. 👁️ Live Preview Tab:
- **Stream Live**: Real-time HD canvas feed.
- **View Mode**: `Camera + HUD`, `HSV Color Mask`, `Split View`.
- **Size**: `360x360`, `400x400`, `320x320`, `256x256`.
- **Live FOV Slider & Popout Window**.

---

## 📜 License
This project is licensed under the GNU GPLv3 License.
