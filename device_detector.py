#!/usr/bin/env python3
"""
Samsung Phone Auto-Detection Engine
Version: 1.0.0 | Build: 20260615

Detects connected Samsung devices and reads:
  - Model number (e.g. SM-S928B)
  - Firmware version (e.g. S928BXXS4AYA1)
  - CSC code (e.g. OXM)
  - Chipset (Exynos/Snapdragon/MediaTek)
  - Android version
  - Bootloader version
  - Serial number
  - Battery level
  - Connection mode (Download/ADB/Fastboot)

Detection methods (in order of reliability):
  1. ADB (ro.product.model, ro.build.display.id, etc.)
  2. Fastboot (getvar all)
  3. Heimdall (PIT read → chipset identification)
  4. USB descriptor cross-reference (VID/PID → known models)
"""

import subprocess
import re
import json
import os
import sys
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════
# USB VID/PID → Model Database
# ═══════════════════════════════════════════════════════════════════════════

# Samsung USB Vendor ID is always 04e8
SAMSUNG_VID = "04e8"

# Known Samsung USB Product IDs by mode
USB_MODE_PIDS = {
    "download": {
        "685d": "Download Mode (Odin)",
        "6860": "Download Mode (Odin alt)",
    },
    "adb": {
        "6860": "Android / ADB",
        "6863": "Android / ADB (debug)",
    },
    "fastboot": {
        "4ee0": "Fastboot / Bootloader",
    },
    "mtp": {
        "6860": "MTP / File Transfer",
        "6864": "MTP (Samsung)",
    },
    "rndis": {
        "6863": "USB Tethering / RNDIS",
    },
}

# Known model → PID mappings for Download Mode
# These are device-specific PIDs that identify the exact model
KNOWN_MODEL_PIDS = {
    # Galaxy S Series
    "SM-S928B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 3", "series": "S24 Ultra"},
    "SM-S928U": {"pid": "685d", "chipset": "Snapdragon 8 Gen 3", "series": "S24 Ultra"},
    "SM-S926B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 3", "series": "S24+"},
    "SM-S921B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 3", "series": "S24"},
    "SM-S918B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "S23 Ultra"},
    "SM-S918U": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "S23 Ultra"},
    "SM-S916B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "S23+"},
    "SM-S911B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "S23 / S23 FE"},
    "SM-S908B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "S22 Ultra"},
    "SM-S908U": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "S22 Ultra"},
    "SM-S906B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "S22+"},
    "SM-S901B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "S22"},
    "SM-S898B": {"pid": "685d", "chipset": "Exynos 2100", "series": "S21 Ultra"},
    "SM-G998B": {"pid": "685d", "chipset": "Exynos 2100", "series": "S21 Ultra"},
    "SM-G996B": {"pid": "685d", "chipset": "Exynos 2100", "series": "S21+"},
    "SM-G991B": {"pid": "685d", "chipset": "Exynos 2100", "series": "S21"},
    "SM-G990B": {"pid": "685d", "chipset": "Exynos 2100", "series": "S21 FE"},
    "SM-G988B": {"pid": "685d", "chipset": "Exynos 990", "series": "S20 Ultra"},
    "SM-G986B": {"pid": "685d", "chipset": "Exynos 990", "series": "S20+"},
    "SM-G981B": {"pid": "685d", "chipset": "Exynos 990", "series": "S20"},
    "SM-G980F": {"pid": "685d", "chipset": "Exynos 9825", "series": "S20 (Exynos)"},
    "SM-G975F": {"pid": "685d", "chipset": "Exynos 9825", "series": "S10+"},
    "SM-G973F": {"pid": "685d", "chipset": "Exynos 9820", "series": "S10"},
    "SM-G970F": {"pid": "685d", "chipset": "Exynos 9820", "series": "S10e"},
    "SM-G965F": {"pid": "685d", "chipset": "Exynos 9810", "series": "S9+"},
    "SM-G960F": {"pid": "685d", "chipset": "Exynos 9810", "series": "S9"},
    "SM-G955F": {"pid": "685d", "chipset": "Exynos 8895", "series": "S8+"},
    "SM-G950F": {"pid": "685d", "chipset": "Exynos 8895", "series": "S8"},

    # Galaxy Note Series
    "SM-N986B": {"pid": "685d", "chipset": "Exynos 990", "series": "Note 20 Ultra"},
    "SM-N981B": {"pid": "685d", "chipset": "Exynos 990", "series": "Note 20"},
    "SM-N975F": {"pid": "685d", "chipset": "Exynos 9825", "series": "Note 10+"},
    "SM-N970F": {"pid": "685d", "chipset": "Exynos 9825", "series": "Note 10"},
    "SM-N960F": {"pid": "685d", "chipset": "Exynos 9810", "series": "Note 9"},
    "SM-N950F": {"pid": "685d", "chipset": "Exynos 8895", "series": "Note 8"},

    # Galaxy Z Series
    "SM-F946B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "Z Fold 5"},
    "SM-F936B": {"pid": "685d", "chipset": "Snapdragon 8+ Gen 1", "series": "Z Fold 4"},
    "SM-F926B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "Z Fold 3"},
    "SM-F731B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "Z Flip 5"},
    "SM-F721B": {"pid": "685d", "chipset": "Snapdragon 8+ Gen 1", "series": "Z Flip 4"},
    "SM-F711B": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "Z Flip 3"},

    # Galaxy A Series
    "SM-A556B": {"pid": "685d", "chipset": "Exynos 1480", "series": "A55 5G"},
    "SM-A546B": {"pid": "685d", "chipset": "Exynos 1380", "series": "A54 5G"},
    "SM-A536B": {"pid": "685d", "chipset": "Exynos 1280", "series": "A53 5G"},
    "SM-A528B": {"pid": "685d", "chipset": "Snapdragon 778G", "series": "A52s 5G"},
    "SM-A525F": {"pid": "685d", "chipset": "Snapdragon 750G", "series": "A52 5G"},
    "SM-A515F": {"pid": "685d", "chipset": "Exynos 9611", "series": "A51"},
    "SM-A505F": {"pid": "685d", "chipset": "Exynos 9611", "series": "A50"},
    "SM-A356B": {"pid": "685d", "chipset": "Exynos 1380", "series": "A35 5G"},
    "SM-A346B": {"pid": "685d", "chipset": "Exynos 1280", "series": "A34"},
    "SM-A336B": {"pid": "685d", "chipset": "Exynos 1280", "series": "A33 5G"},
    "SM-A326B": {"pid": "685d", "chipset": "Helio G80", "series": "A32"},
    "SM-A266B": {"pid": "685d", "chipset": "Exynos 1280", "series": "A26 5G"},
    "SM-A256B": {"pid": "685d", "chipset": "Exynos 1280", "series": "A25"},
    "SM-A245F": {"pid": "685d", "chipset": "Helio G99", "series": "A24"},
    "SM-A236B": {"pid": "685d", "chipset": "Snapdragon 680", "series": "A23 5G"},
    "SM-A156B": {"pid": "685d", "chipset": "Helio G99", "series": "A15 5G"},
    "SM-A146B": {"pid": "685d", "chipset": "Exynos 1330", "series": "A14 5G"},
    "SM-A136B": {"pid": "685d", "chipset": "Exynos 850", "series": "A13"},
    "SM-A057F": {"pid": "685d", "chipset": "Helio G85", "series": "A05"},
    "SM-A045F": {"pid": "685d", "chipset": "Helio G35", "series": "A04"},
    "SM-A042F": {"pid": "685d", "chipset": "Helio G85", "series": "A04e"},
    "SM-A037F": {"pid": "685d", "chipset": "Helio G35", "series": "A03s"},
    "SM-A035F": {"pid": "685d", "chipset": "Helio G35", "series": "A03"},
    "SM-A025F": {"pid": "685d", "chipset": "Helio P22", "series": "A02s"},
    "SM-A015F": {"pid": "685d", "chipset": "Helio A22", "series": "A01"},

    # Galaxy M Series
    "SM-M546B": {"pid": "685d", "chipset": "Exynos 1380", "series": "M54 5G"},
    "SM-M536B": {"pid": "685d", "chipset": "Dimensity 900", "series": "M53 5G"},
    "SM-M346B": {"pid": "685d", "chipset": "Exynos 1280", "series": "M34 5G"},
    "SM-M336B": {"pid": "685d", "chipset": "Exynos 1280", "series": "M33 5G"},
    "SM-M236B": {"pid": "685d", "chipset": "Snapdragon 695", "series": "M23 5G"},
    "SM-M135F": {"pid": "685d", "chipset": "Exynos 850", "series": "M13"},
    "SM-M127F": {"pid": "685d", "chipset": "Snapdragon 450", "series": "M12"},

    # Galaxy F Series
    "SM-E546B": {"pid": "685d", "chipset": "Exynos 1380", "series": "F54 5G"},
    "SM-E346B": {"pid": "685d", "chipset": "Exynos 1380", "series": "F34 5G"},

    # Galaxy Tab Series
    "SM-X900": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "Tab S9 Ultra"},
    "SM-X800": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "Tab S9+"},
    "SM-X700": {"pid": "685d", "chipset": "Snapdragon 8 Gen 2", "series": "Tab S9"},
    "SM-T970": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "Tab S8 Ultra"},
    "SM-T870": {"pid": "685d", "chipset": "Snapdragon 8 Gen 1", "series": "Tab S8"},
    "SM-T730": {"pid": "685d", "chipset": "Snapdragon 870", "series": "Tab S7 FE"},
    "SM-T500": {"pid": "685d", "chipset": "Exynos 9611", "series": "Tab A7"},
    "SM-T290": {"pid": "685d", "chipset": "Snapdragon 429", "series": "Tab A 8.0"},
}


# ═══════════════════════════════════════════════════════════════════════════
# Detection Result
# ═══════════════════════════════════════════════════════════════════════════

class DeviceInfo:
    """Complete device detection result."""

    def __init__(self):
        self.detected = False
        self.model = ""
        self.model_name = ""
        self.serial = ""
        self.firmware = ""
        self.csc = ""
        self.chipset = ""
        self.android_version = ""
        self.bootloader_version = ""
        self.binary_version = ""
        self.security_patch = ""
        self.battery_level = ""
        self.connection_mode = ""
        self.usb_vid = ""
        self.usb_pid = ""
        self.usb_location = ""
        self.imei = ""
        self.carrier = ""
        self.detection_method = ""
        self.errors = []
        self.raw_props = {}

    def to_dict(self) -> dict:
        return {
            "detected": self.detected,
            "model": self.model,
            "model_name": self.model_name,
            "serial": self.serial,
            "firmware": self.firmware,
            "csc": self.csc,
            "chipset": self.chipset,
            "android_version": self.android_version,
            "bootloader_version": self.bootloader_version,
            "binary_version": self.binary_version,
            "security_patch": self.security_patch,
            "battery_level": self.battery_level,
            "connection_mode": self.connection_mode,
            "usb_vid": self.usb_vid,
            "usb_pid": self.usb_pid,
            "usb_location": self.usb_location,
            "imei": self.imei,
            "carrier": self.carrier,
            "detection_method": self.detection_method,
            "errors": self.errors,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Detection Methods
# ═══════════════════════════════════════════════════════════════════════════

def _run_cmd(cmd: list, timeout: int = 10) -> tuple:
    """Run a command and return (stdout, stderr, returncode)."""
    try:
        env = os.environ.copy()
        # Ensure /usr/local/bin is in PATH (heimdall, adb, fastboot location)
        if '/usr/local/bin' not in env.get('PATH', ''):
            env['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:' + env.get('PATH', '')
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except Exception as e:
        return "", str(e), -1


def detect_usb_devices() -> list:
    """Detect Samsung USB devices via ioreg (more reliable than system_profiler)."""
    devices = []
    stdout, stderr, rc = _run_cmd(['ioreg', '-p', 'IOUSB', '-w0', '-l'], timeout=10)
    if rc != 0:
        # Fallback to system_profiler
        return detect_usb_devices_sp()

    # Parse ioreg output for Samsung devices
    current = {}
    for line in stdout.split('\n'):
        s = line.strip()
        if '"idVendor"' in s:
            match = re.search(r'"idVendor"\s*=\s*(\d+)', s)
            if match:
                current['vendor_id'] = format(int(match.group(1)), '04x')
        elif '"idProduct"' in s:
            match = re.search(r'"idProduct"\s*=\s*(\d+)', s)
            if match:
                current['product_id'] = format(int(match.group(1)), '04x')
        elif '"USB Product Name"' in s and 'SAMSUNG' in s.upper():
            current['manufacturer'] = 'Samsung Electronics'
        elif '"USB Vendor Name"' in s and 'SAMSUNG' in s.upper():
            current['manufacturer'] = 'Samsung Electronics'
        elif '"USB Serial Number"' in s:
            match = re.search(r'"USB Serial Number"\s*=\s*"?([^"]+)"?', s)
            if match:
                current['serial'] = match.group(1).strip()
        elif '"locationID"' in s:
            match = re.search(r'"locationID"\s*=\s*(0x[0-9a-fA-F]+)', s)
            if match:
                current['location'] = match.group(1)
                # End of device block — save if Samsung
                if current.get('vendor_id', '').lower() == SAMSUNG_VID:
                    devices.append(current)
                current = {}

    # Catch last device
    if current.get('vendor_id', '').lower() == SAMSUNG_VID:
        devices.append(current)

    return devices


def detect_usb_devices_sp() -> list:
    """Fallback: detect Samsung USB devices via system_profiler."""
    devices = []
    stdout, stderr, rc = _run_cmd(['system_profiler', 'SPUSBDataType'], timeout=10)
    if rc != 0:
        return devices

    lines = stdout.split('\n')
    current = {}
    for line in lines:
        s = line.strip()
        if 'SAMSUNG' in s.upper() or 'Samsung' in s:
            current['manufacturer'] = 'Samsung Electronics'
        if 'Product ID:' in s:
            current['product_id'] = s.split(':')[-1].strip().lstrip('0x')
        if 'Vendor ID:' in s:
            current['vendor_id'] = s.split(':')[-1].strip().lstrip('0x')
        if 'Serial Number:' in s:
            current['serial'] = s.split(':')[-1].strip()
        if 'Location ID:' in s and current.get('product_id'):
            current['location'] = s.split(':')[-1].strip()
            if current.get('vendor_id', '').lower() == SAMSUNG_VID:
                devices.append(current)
            current = {}
    return devices


def detect_via_adb() -> Optional[DeviceInfo]:
    """
    Detect device via ADB (Android mode).
    This is the most reliable method — reads all properties directly.
    """
    # Check if ADB is available and device is connected
    stdout, stderr, rc = _run_cmd(['adb', 'devices'], timeout=5)
    if rc != 0:
        return None

    # Check for connected device (not just "List of devices attached")
    lines = [l for l in stdout.split('\n') if l.strip() and 'List of' not in l]
    device_lines = [l for l in lines if '\tdevice' in l or '\trecovery' in l]
    if not device_lines:
        return None

    info = DeviceInfo()
    info.detected = True
    info.connection_mode = "ADB"
    info.detection_method = "ADB getprop"

    # Read all relevant properties
    props_to_read = [
        'ro.product.model',
        'ro.product.name',
        'ro.product.brand',
        'ro.product.device',
        'ro.build.display.id',
        'ro.build.version.release',
        'ro.build.version.security_patch',
        'ro.build.version.sdk',
        'ro.bootloader',
        'ro.hardware',
        'ro.board.platform',
        'ro.csc.sales_code',
        'ro.csc.country_code',
        'ro.csc.countryiso_code',
        'ro.serialno',
        'ro.build.user',
        'ro.build.host',
        'ro.build.date',
        'ro.build.type',
        'ro.secure',
        'ro.debuggable',
        'ro.boot.hardware.chipset',
        'ro.boot.hardware',
        'persist.sys.usb.config',
        'gsm.sim.operator.alpha',
        'gsm.operator.alpha',
        'gsm.sim.state',
        'ro.carrier',
        'ro.com.google.clientidbase',
        'ro.build.flavor',
        'ro.product.cpu.abi',
        'ro.product.cpu.abilist',
        'ro.chipname',
        'ro.arch',
        'ro.hardware.egl',
        'ro.boot.serial',
        'ril.serialnumber',
        'ro.ril.oem.sno',
        'ro.ril.oem.meid',
        'ro.imei',
        'persist.radio.imei',
        'gsm.imei',
    ]

    for prop in props_to_read:
        stdout, _, _ = _run_cmd(['adb', 'shell', 'getprop', prop], timeout=5)
        if stdout:
            info.raw_props[prop] = stdout

    # Parse properties
    info.model = info.raw_props.get('ro.product.model', '')
    info.serial = info.raw_props.get('ro.serialno', '') or info.raw_props.get('ro.boot.serial', '')
    info.firmware = info.raw_props.get('ro.build.display.id', '')
    info.android_version = info.raw_props.get('ro.build.version.release', '')
    info.security_patch = info.raw_props.get('ro.build.version.security_patch', '')
    info.bootloader_version = info.raw_props.get('ro.bootloader', '')
    info.csc = info.raw_props.get('ro.csc.sales_code', '')
    info.carrier = info.raw_props.get('gsm.sim.operator.alpha', '') or info.raw_props.get('ro.carrier', '')

    # Chipset detection
    chipset = info.raw_props.get('ro.boot.hardware.chipset', '') or info.raw_props.get('ro.board.platform', '') or info.raw_props.get('ro.hardware', '')
    info.chipset = chipset

    # Binary version from firmware string
    if info.firmware and len(info.firmware) >= 9:
        info.binary_version = info.firmware[8]

    # Model name from known database
    if info.model in KNOWN_MODEL_PIDS:
        info.model_name = KNOWN_MODEL_PIDS[info.model].get('series', '')
        if not info.chipset:
            info.chipset = KNOWN_MODEL_PIDS[info.model].get('chipset', '')

    # Battery level
    stdout, _, _ = _run_cmd(['adb', 'shell', 'dumpsys', 'battery'], timeout=5)
    if stdout:
        match = re.search(r'level:\s*(\d+)', stdout)
        if match:
            info.battery_level = match.group(1) + '%'

    # IMEI
    if not info.imei:
        stdout, _, _ = _run_cmd(['adb', 'shell', 'service', 'call', 'iphonesubinfo', '1'], timeout=5)
        if stdout:
            # Parse IMEI from service call output
            digits = re.findall(r"'(\d+)'", stdout)
            if digits:
                imei_str = ''.join(digits).replace("'", "")
                if len(imei_str) >= 15:
                    info.imei = imei_str[:15]

    return info


def detect_via_fastboot() -> Optional[DeviceInfo]:
    """
    Detect device via Fastboot (Bootloader mode).
    Reads variables from the bootloader.
    """
    stdout, stderr, rc = _run_cmd(['fastboot', 'devices'], timeout=5)
    if rc != 0 or not stdout.strip():
        return None

    info = DeviceInfo()
    info.detected = True
    info.connection_mode = "Fastboot"
    info.detection_method = "Fastboot getvar"

    # Get all fastboot variables
    stdout, _, rc = _run_cmd(['fastboot', 'getvar', 'all'], timeout=10)
    if rc != 0:
        info.errors.append("Failed to read fastboot variables")
        return info

    # Parse fastboot output
    for line in stdout.split('\n'):
        match = re.match(r'\((\w+)\):\s*(.+)', line)
        if match:
            key, value = match.group(1), match.group(2)
            info.raw_props[f'fb.{key}'] = value

    info.model = info.raw_props.get('fb.product', '') or info.raw_props.get('fb.device', '')
    info.serial = info.raw_props.get('fb.serialno', '')
    info.bootloader_version = info.raw_props.get('fb.bootloader', '')
    info.chipset = info.raw_props.get('fb.chipname', '') or info.raw_props.get('fb.platform', '')

    # Secure boot status
    secure = info.raw_props.get('fb.secure', '')
    if secure == 'yes':
        info.raw_props['_secure_boot'] = 'Enabled'
    elif secure == 'no':
        info.raw_props['_secure_boot'] = 'Disabled'

    # Model name from known database
    if info.model in KNOWN_MODEL_PIDS:
        info.model_name = KNOWN_MODEL_PIDS[info.model].get('series', '')

    return info


def detect_via_heimdall() -> Optional[DeviceInfo]:
    """
    Detect device via Heimdall (Download Mode).
    Reads PIT to identify chipset and device info.
    """
    stdout, stderr, rc = _run_cmd(['heimdall', 'detect'], timeout=10)
    if rc != 0:
        return None

    info = DeviceInfo()
    info.detected = True
    info.connection_mode = "Download Mode (Odin)"
    info.detection_method = "Heimdall"

    # Try to read PIT
    pit_stdout, pit_stderr, pit_rc = _run_cmd(['heimdall', 'print-pit', '--no-reboot'], timeout=30)
    if pit_rc == 0 and pit_stdout:
        info.raw_props['pit_output'] = pit_stdout
        info.detection_method = "Heimdall PIT"

        # Parse PIT for chipset identification
        pit_upper = pit_stdout.upper()
        if 'MTK' in pit_upper or 'MEDIATEK' in pit_upper:
            info.chipset = "MediaTek"
        elif 'UFS' in pit_upper:
            info.raw_props['_storage'] = 'UFS'
        elif 'EMMC' in pit_upper:
            info.raw_props['_storage'] = 'eMMC'

        # Parse partition count
        match = re.search(r'Entry Count:\s*(\d+)', pit_stdout)
        if match:
            info.raw_props['_partition_count'] = match.group(1)

        # Parse storage type
        match = re.search(r'Device Type:\s*(\d+)\s*\((\w+)\)', pit_stdout)
        if match:
            info.raw_props['_device_type'] = match.group(2)
    else:
        # Heimdall detected but PIT read failed (common on 2020+ devices)
        if pit_stderr and 'Failed to send' in pit_stderr:
            info.errors.append("Heimdall PIT read failed — 2020+ device detected. Use Odin on Windows for full access.")
            info.detection_method = "Heimdall (detect only, PIT read failed)"
        info.raw_props['pit_error'] = pit_stderr

    return info


def detect_via_usb_descriptor() -> Optional[DeviceInfo]:
    """
    Fallback: detect device via USB descriptors only.
    Can identify mode but not exact model without additional queries.
    Cross-references PID against known model database.
    """
    usb_devices = detect_usb_devices()
    if not usb_devices:
        return None

    # Find Samsung devices
    samsung_devs = [d for d in usb_devices if d.get('vendor_id', '').lower() == SAMSUNG_VID]
    if not samsung_devs:
        return None

    info = DeviceInfo()
    info.detected = True
    info.connection_mode = "USB (descriptor)"
    info.detection_method = "USB VID/PID"

    dev = samsung_devs[0]
    info.usb_vid = dev.get('vendor_id', '')
    info.usb_pid = dev.get('product_id', '')
    info.usb_location = dev.get('location', '')
    info.serial = dev.get('serial', '')

    pid = info.usb_pid.lower()
    if pid in USB_MODE_PIDS.get('download', {}):
        info.connection_mode = USB_MODE_PIDS['download'][pid]
    elif pid in USB_MODE_PIDS.get('adb', {}):
        info.connection_mode = USB_MODE_PIDS['adb'][pid]
    elif pid in USB_MODE_PIDS.get('fastboot', {}):
        info.connection_mode = USB_MODE_PIDS['fastboot'][pid]

    # Cross-reference PID against known model database
    # NOTE: PID 685d is shared by ALL Samsung devices in Download Mode
    # so we cannot identify the exact model from USB descriptors alone.
    # The model can only be read via ADB (ro.product.model) or fastboot.
    if pid == '685d':
        # Generic Download Mode — model requires ADB/fastboot to identify
        info.model = ""
        info.model_name = ""
        info.chipset = ""
        info.detection_method = "USB VID/PID (Download Mode)"
    elif pid == '4ee0':
        info.model = ""
        info.model_name = ""
        info.chipset = ""
        info.detection_method = "USB VID/PID (Fastboot)"
    else:
        # Try to match specific PIDs (rare — most Samsung devices share 685d)
        for model, data in KNOWN_MODEL_PIDS.items():
            if data.get('pid', '').lower() == pid:
                info.model = model
                info.model_name = data.get('series', '')
                info.chipset = data.get('chipset', '')
                info.detection_method = "USB VID/PID + model DB"
                break

    return info


# ═══════════════════════════════════════════════════════════════════════════
# Main Detection Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def detect_device() -> DeviceInfo:
    """
    Run full auto-detection across all methods.
    Returns the most complete DeviceInfo available.
    Merges data from multiple methods when possible.
    """
    info = DeviceInfo()

    # Method 1: ADB (most reliable — full property read)
    try:
        adb_info = detect_via_adb()
        if adb_info and adb_info.detected:
            return adb_info
    except Exception as e:
        info.errors.append(f"ADB detection failed: {e}")

    # Method 2: Fastboot
    try:
        fastboot_info = detect_via_fastboot()
        if fastboot_info and fastboot_info.detected:
            # Enrich with USB descriptor
            usb_info = detect_via_usb_descriptor()
            if usb_info and not fastboot_info.model and usb_info.model:
                fastboot_info.model = usb_info.model
                fastboot_info.model_name = usb_info.model_name
                fastboot_info.chipset = usb_info.chipset
            return fastboot_info
    except Exception as e:
        info.errors.append(f"Fastboot detection failed: {e}")

    # Method 3: Heimdall (Download Mode)
    try:
        heimdall_info = detect_via_heimdall()
        if heimdall_info and heimdall_info.detected:
            # Enrich with USB descriptor for model identification
            usb_info = detect_via_usb_descriptor()
            if usb_info:
                if not heimdall_info.model and usb_info.model:
                    heimdall_info.model = usb_info.model
                    heimdall_info.model_name = usb_info.model_name
                if not heimdall_info.chipset and usb_info.chipset:
                    heimdall_info.chipset = usb_info.chipset
                if usb_info.usb_vid:
                    heimdall_info.usb_vid = usb_info.usb_vid
                if usb_info.usb_pid:
                    heimdall_info.usb_pid = usb_info.usb_pid
                if usb_info.serial:
                    heimdall_info.serial = usb_info.serial
            return heimdall_info
    except Exception as e:
        info.errors.append(f"Heimdall detection failed: {e}")

    # Method 4: USB descriptor (fallback)
    try:
        usb_info = detect_via_usb_descriptor()
        if usb_info and usb_info.detected:
            return usb_info
    except Exception as e:
        info.errors.append(f"USB detection failed: {e}")

    # Nothing found
    info.detected = False
    info.errors.append("No Samsung device detected on any interface")
    return info


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def format_device_info(info: DeviceInfo) -> str:
    """Format device info as human-readable string."""
    if not info.detected:
        return "No Samsung device detected.\nErrors: " + "; ".join(info.errors)

    lines = [
        "═══════════════════════════════════════════════════",
        "  SAMSUNG DEVICE AUTO-DETECTION",
        "═══════════════════════════════════════════════════",
        "",
        f"  Model:           {info.model or 'Unknown'}",
        f"  Model Name:      {info.model_name or 'Unknown'}",
        f"  Serial:          {info.serial or 'N/A'}",
        f"  Firmware:        {info.firmware or 'N/A'}",
        f"  CSC:             {info.csc or 'N/A'}",
        f"  Chipset:         {info.chipset or 'N/A'}",
        f"  Android:         {info.android_version or 'N/A'}",
        f"  Bootloader:      {info.bootloader_version or 'N/A'}",
        f"  Binary Version:  {info.binary_version or 'N/A'}",
        f"  Security Patch:  {info.security_patch or 'N/A'}",
        f"  Battery:         {info.battery_level or 'N/A'}",
        f"  Carrier:         {info.carrier or 'N/A'}",
        f"  IMEI:            {info.imei or 'N/A'}",
        f"  Connection:      {info.connection_mode}",
        f"  USB ID:          {info.usb_vid}:{info.usb_pid}" if info.usb_vid else "",
        f"  Detection:       {info.detection_method}",
        "",
        "═══════════════════════════════════════════════════",
    ]
    return "\n".join(line for line in lines if line)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Samsung Phone Auto-Detection")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--method", choices=["adb", "fastboot", "heimdall", "usb", "auto"],
                        default="auto", help="Detection method")
    args = parser.parse_args()

    if args.method == "adb":
        info = detect_via_adb() or DeviceInfo()
    elif args.method == "fastboot":
        info = detect_via_fastboot() or DeviceInfo()
    elif args.method == "heimdall":
        info = detect_via_heimdall() or DeviceInfo()
    elif args.method == "usb":
        info = detect_via_usb_descriptor() or DeviceInfo()
    else:
        info = detect_device()

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
    else:
        print(format_device_info(info))


if __name__ == "__main__":
    main()
