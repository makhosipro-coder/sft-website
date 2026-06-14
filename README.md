# SFT — Samsung Firmware Tool

**Samsung Firmware Tool (SFT)** — Local USB device detection, firmware management, and flashing guidance for Samsung Galaxy devices.

![Version](https://img.shields.io/badge/version-2.5.1-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Android-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Build](https://img.shields.io/badge/build-passing-brightgreen)

🔗 **Live Demo**: https://sft-sprutting.netlify.app (pending setup)
📦 **GitHub**: https://github.com/makhosipro-coder/sft-website

## Features

- **🔍 Auto-Detection**: Detects connected Samsung devices via ADB, Fastboot, Heimdall (PIT read), and USB descriptors
- **📊 Device Status**: Live dashboard showing model, serial, firmware, CSC, chipset, battery, and connection mode
- **🔧 Firmware Decoder**: Parses 13-character Samsung firmware strings into hardware, market, update, and build segments
- **🛡️ Rollback Prevention**: Hardware mismatch, chipset mismatch, and bootloader version checks
- **🌍 CSC Database**: 237+ Country Specific Codes with carrier, region, Samsung Pay, VoLTE, and 5G support
- **📱 Flash Guide**: Step-by-step Odin flashing instructions with model-specific guidance
- **✅ Firmware Validation**: tar.md5 integrity verification and content listing
- **🔄 FOTA Checker**: Queries Samsung's firmware servers for latest available builds
- **📲 Android APK**: Native Android app via Kivy WebView wrapper

## Quick Start

### Local Development
```bash
git clone https://github.com/makhosipro-coder/sft-website.git
cd sft-website
pip3 install flask requests
python3 app.py
```
Open http://localhost:5000

### Prerequisites
- Python 3.9+
- Flask, requests
- Heimdall (Download Mode detection): `brew install heimdall`
- ADB (Android mode): `brew install android-platform-tools`

## Project Structure

```
sft-website/
├── app.py                  # Flask application
├── device_detector.py      # Samsung device auto-detection engine
├── firmware_parser.py      # 13-char firmware string parser
├── fota_checker.py         # FOTA XML firmware checker
├── csc_database.json       # 237+ CSC codes database
├── android_main.py         # Android Kivy WebView wrapper
├── buildozer.spec          # Android APK build config
├── netlify.toml            # Netlify deployment config
├── package.json            # Node.js metadata
├── run.py                  # Development server launcher
├── scripts/
│   ├── daily_update.sh     # Automated daily sync (cron)
│   └── deploy.sh           # GitHub + Netlify deployment
├── templates/              # 11 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── device_status.html
│   ├── flash_guide.html
│   ├── firmware_table.html
│   ├── reset_wizard.html
│   ├── removal.html
│   ├── test.html
│   ├── override.html
│   ├── safety_guide.html
│   └── coming_soon.html
├── static/
│   ├── css/style.css
│   └── js/app.js
└── README.md
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/device/detect` | GET | Full auto-detect (ADB→Fastboot→Heimdall→USB) |
| `/api/device/status` | GET | Quick connection check |
| `/api/device/adb` | GET | ADB-only detection |
| `/api/device/fastboot` | GET | Fastboot-only detection |
| `/api/device/heimdall` | GET | Heimdall-only detection |
| `/api/device/models` | GET | List known Samsung models (82 entries) |
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

## Supported Devices

| Series | Models | Chipset | macOS Flash |
|--------|--------|---------|-------------|
| Galaxy S24 | S928B, S926B, S921B | Snapdragon 8 Gen 3 | ❌ Windows only |
| Galaxy S23 | S918B, S916B, S911B | Snapdragon 8 Gen 2 | ❌ Windows only |
| Galaxy Z Fold/Flip 5 | F946B, F731B | Snapdragon | ❌ Windows only |
| Galaxy A55/A54 | A556B, A546B | Exynos | ❌ Windows only |
| Galaxy A04e | A042F | MediaTek G85 | ❌ Windows only |
| Galaxy A35/A34 | A356B, A346B | Exynos | ❌ Windows only |

**Note**: MediaTek devices require Odin on Windows. macOS/Linux tools can detect but not flash.

## Android APK

Build the standalone Android app:
```bash
pip install buildozer
buildozer android debug
```

## Daily Updates

Automated daily sync via cron (9am):
```bash
crontab -e
# Add: 0 9 * * * /Users/editsuite/sft-website/scripts/daily_update.sh
```

## License

MIT License — Not affiliated with Samsung Electronics Co., Ltd.
