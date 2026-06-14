# SFT — Samsung Firmware Tool

**Samsung Firmware Tool (SFT)** — Local USB device detection, firmware management, and flashing guidance for Samsung Galaxy devices.

![Version](https://img.shields.io/badge/version-2.5.0-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Auto-Detection**: Detects connected Samsung devices via ADB, Fastboot, Heimdall (PIT read), and USB descriptors
- **Device Status**: Live dashboard showing model, serial, firmware, CSC, chipset, battery, and connection mode
- **Firmware Decoder**: Parses 13-character Samsung firmware strings into hardware, market, update, and build segments
- **Rollback Prevention**: Hardware mismatch, chipset mismatch, and bootloader version checks
- **CSC Database**: 237+ Country Specific Codes with carrier, region, Samsung Pay, VoLTE, and 5G support
- **Flash Guide**: Step-by-step Odin flashing instructions with model-specific guidance
- **Firmware Validation**: tar.md5 integrity verification and content listing
- **FOTA Checker**: Queries Samsung's firmware servers for latest available builds

## Supported Devices

| Series | Models | Chipset | macOS Flash |
|--------|--------|---------|-------------|
| Galaxy S24 | S928B, S926B, S921B | Snapdragon 8 Gen 3 | ❌ Windows only |
| Galaxy S23 | S918B, S916B, S911B | Snapdragon 8 Gen 2 | ❌ Windows only |
| Galaxy S22 | S908B, S906B, S901B | Snapdragon 8 Gen 1 | ❌ Windows only |
| Galaxy Z Fold 5/4 | F946B, F936B | Snapdragon | ❌ Windows only |
| Galaxy Z Flip 5/4 | F731B, F721B | Snapdragon | ❌ Windows only |
| Galaxy A55/A54 | A556B, A546B | Exynos | ❌ Windows only |
| Galaxy A04e | A042F | MediaTek G85 | ❌ Windows only |
| Galaxy A35/A34 | A356B, A346B | Exynos | ❌ Windows only |

**Note**: MediaTek devices (A04e, A03, A02, etc.) require Odin on Windows. macOS/Linux tools can detect but not flash these devices.

## Quick Start

### Prerequisites
- Python 3.9+
- Flask
- Heimdall (for Download Mode detection): `brew install heimdall`
- ADB (for Android mode detection): `brew install android-platform-tools`

### Installation

```bash
git clone https://github.com/sprutting/sft-website.git
cd sft-website
pip3 install flask
python3 app.py
```

Open http://localhost:5000 in your browser.

## Project Structure

```
sft-website/
├── app.py                  # Flask application (main entry)
├── device_detector.py      # Samsung device auto-detection engine
├── firmware_parser.py      # 13-char firmware string parser
├── fota_checker.py         # FOTA XML firmware checker
├── csc_database.json       # 237+ CSC codes database
├── run.py                  # Development server launcher
├── templates/
│   ├── base.html           # Base template with nav
│   ├── index.html          # Home page with live device console
│   ├── device_status.html  # Live device status dashboard
│   ├── flash_guide.html    # Step-by-step Odin flash guide
│   ├── firmware_table.html # Firmware compatibility table
│   ├── reset_wizard.html   # Guided reset workflow
│   ├── removal.html        # Firmware removal procedures
│   ├── test.html           # Diagnostic test suite
│   ├── override.html       # Override command system
│   ├── safety_guide.html   # Safety documentation
│   └── coming_soon.html    # Placeholder page
├── static/
│   ├── css/style.css       # Main stylesheet
│   └── js/app.js           # Frontend JavaScript
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/device/detect` | GET | Full auto-detect (ADB→Fastboot→Heimdall→USB) |
| `/api/device/status` | GET | Quick connection check |
| `/api/device/adb` | GET | ADB-only detection |
| `/api/device/fastboot` | GET | Fastboot-only detection |
| `/api/device/heimdall` | GET | Heimdall-only detection |
| `/api/device/models` | GET | List known Samsung models |
| `/api/firmware/validate` | POST | Validate tar.md5 firmware file |
| `/api/command` | POST | Execute ADB/fastboot/heimdall command |
| `/api/heimdall/pit` | GET | Read PIT via Heimdall |
| `/api/adb/getprop` | GET | Get device property via ADB |

## Firmware String Format

Samsung firmware strings are 13 characters: `XXXXXYYYZZAAABBB`

```
S928BXXS4AYA1
│    ││ │ ││└─ Sub-revision
│    ││ │ │└── Build sequence
│    ││ │ └─── Month code (A=Jan, B=Feb, ..., L=Dec)
│    ││ └───── Type (S=Security, U=Major, etc.) + Year (A=2024, B=2025, ...)
│    │└─────── Binary/bootloader version (0-9, A=10, B=11, ...)
│    └──────── CSC/region code (OXM=Europe, XAA=USA, INS=India, etc.)
└───────────── Hardware: Series (S=Galaxy S) + Model (928) + Variant (B=International)
```

## License

MIT License — Not affiliated with Samsung Electronics Co., Ltd.
