# Touchless Gesture Tracking & Overlay System

Real-time 21-landmark hand gesture tracking and visual feedback overlay system engineered for interactive kiosks and desktop applications on **Raspberry Pi (Linux)** and **Windows**.

---

## 📐 Project Architecture & Directory Layout

This repository contains multi-platform implementations tailored for Linux/Raspberry Pi hardware and Windows desktop environments:

```
python-v1/
├── Raspberrypi/           # Linux & Raspberry Pi kiosk implementation
│   ├── gesture_engine.py  # Headless hand-tracking engine & WebSocket server
│   ├── overlay.py         # Transparent PyQt5 overlay client
│   ├── setup_pi.sh        # System setup & environment provisioning script
│   ├── install.sh         # Dependencies installation script
│   ├── install_services.sh# Systemd service creation for kiosk deployment
│   ├── restart.sh         # Kiosk service restarter script
│   ├── system_architecture_report.md  # Detailed technical report & parameter reference
│   └── README.md          # Raspberry Pi documentation
│
└── Windows_Version/       # Windows 10/11 desktop implementation
    ├── gesture_engine.py  # High-DPI aware tracking engine & unified runner
    ├── overlay.py         # Transparent PyQt5 skeleton & dwell UI
    ├── hand_landmarker.task # MediaPipe Tasks 3D hand landmarker model
    ├── requirements.txt   # Windows Python dependencies
    └── README.md          # Windows documentation
```

---

## 🌟 Core System Capabilities

- **Real-Time 21-Landmark Hand Tracking**: Uses MediaPipe Tasks API (`HandLandmarker`) for low-latency 3D hand tracking.
- **Dwell-to-Click State Machine**: Triggers system click events when holding position over interactive UI elements for a set duration, with built-in cooldown and ghost-click protection.
- **OneEuro Cursor Filtering**: Removes hand micro-tremors and tracking jitter without introduces phase lag.
- **Transparent Visual Feedback**: Click-through PyQt5 overlay displaying real-time hand skeleton and dwell progress arc.
- **WebSocket Streaming**: Asynchronous JSON event broadcast (`ws://localhost:8765`) enabling decoupled multi-process architecture.

---

## 🖥️ Platform Quick Start

### 1. Raspberry Pi / Linux Setup
For Raspberry Pi OS, Linux X11, or Wayland setups:

```bash
cd Raspberrypi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gesture_engine.py
```
> For complete deployment details and systemd kiosk service installation, see [`Raspberrypi/README.md`](file:///C:/Users/kito/python-v1/Raspberrypi/README.md) and [`Raspberrypi/system_architecture_report.md`](file:///C:/Users/kito/python-v1/Raspberrypi/system_architecture_report.md).

### 2. Windows Setup
For Windows 10 / 11 desktop environments:

```powershell
cd Windows_Version
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python gesture_engine.py
```
> For Windows High-DPI details and Win32 native mouse fallback configuration, see [`Windows_Version/README.md`](file:///C:/Users/kito/python-v1/Windows_Version/README.md).

