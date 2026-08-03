# Windows Gesture Engine & Transparent Overlay Kiosk

A real-time hand gesture tracking engine and transparent visual feedback overlay optimized for Windows 10/11 desktop and kiosk environments.

---

## 🌟 Overview

The **Windows Version** provides low-latency 21-landmark hand tracking, movement smoothing, dwell-to-click gesture recognition, and a click-through transparent PyQt5 overlay UI. It is engineered specifically for Windows with High-DPI display support, native Windows API input injection, and unified event loop scheduling.

---

## ✨ Key Features & Windows Optimizations

- **High-DPI Awareness**: Automatically sets process DPI awareness via `shcore.dll` (`Per-Monitor DPI Aware v2`) / `user32.dll` to prevent scaling blur on 4K/high-res displays.
- **Native Input Injection Fallback**: Uses `ctypes.windll.user32` (`SetCursorPos` and `mouse_event`) for OS mouse click simulation when `pynput` is not installed or lacks administrative context.
- **MediaPipe Tasks API**: Utilizes the 3D `hand_landmarker.task` model for robust single-hand tracking.
- **Unified Single-Process Execution**: Uses `qasync` to combine Qt's event loop with Python `asyncio` inside `gesture_engine.py`.
- **OneEuro & Tremor Filtering**: Smooths index fingertip tracking to eliminate cursor jitter without introducing lag.
- **Click-Through PyQt5 Overlay**: Uses `Qt.WindowTransparentForInput` and `Qt.WA_TranslucentBackground` so mouse clicks pass directly to underlying OS windows.
- **WebSocket Streaming**: Broadcasts live landmark data and gesture states over `ws://127.0.0.1:8765`.

---

## 📋 Requirements

- **Operating System**: Windows 10 / Windows 11 (64-bit)
- **Python**: Version 3.8 or newer
- **Hardware**: Standard USB Webcam or integrated camera

### Python Dependencies (`requirements.txt`)
- `opencv-python`
- `mediapipe`
- `PyQt5`
- `qasync`
- `websockets`
- `pynput`
- `numpy`

---

## 🚀 Quick Start

### 1. Set Up Virtual Environment

Open PowerShell or Command Prompt in the `Windows_Version` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the Application

Start the unified gesture engine and transparent overlay:

```powershell
python gesture_engine.py
```

*Optionally, to run the transparent overlay client in standalone WebSocket mode:*

```powershell
python overlay.py
```

---

## 📁 File Structure

| File | Description |
| :--- | :--- |
| [`gesture_engine.py`](file:///C:/Users/kito/python-v1/Windows_Version/gesture_engine.py) | Main background gesture tracking engine, MediaPipe integration, OneEuro filtering, and unified `qasync` application runner. |
| [`overlay.py`](file:///C:/Users/kito/python-v1/Windows_Version/overlay.py) | Transparent PyQt5 window that renders the 21-landmark hand skeleton and dwell progress indicator. |
| `hand_landmarker.task` | Pre-configured MediaPipe 3D Hand Landmarker model file. |
| [`requirements.txt`](file:///C:/Users/kito/python-v1/Windows_Version/requirements.txt) | Python dependencies required for Windows setup. |

---

## ⚙️ Configuration & Tuning

Key configuration parameters inside `gesture_engine.py`:

- **`CAMERA_INDEX`**: Index of camera device (default: `0`).
- **`CAMERA_WIDTH` / `CAMERA_HEIGHT`**: Capture resolution (default: `640x480`).
- **`TARGET_FPS`**: Target frame rate (default: `60`).
- **`DWELL_DURATION_S`**: Required hover duration for dwell-to-click trigger (default: `1.2s`).
- **`DWELL_RADIUS_PX`**: Maximum allowed hover drift in pixels (default: `48px`).
- **`WS_URI`**: WebSocket URI (default: `ws://127.0.0.1:8765`).
