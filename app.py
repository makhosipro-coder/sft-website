#!/usr/bin/env python3
"""
SFT — Samsung Firmware Tool
Main Application Entry Point
Version: 3.0.0 | Build: 20260615

Integrates:
- Backend database (SQLite)
- REST API v1 with auth
- Device detection
- Firmware parsing
- CSC database
"""

import os
import sys
import time
import json
import subprocess
import re

from flask import Flask, render_template, jsonify, request

# ─── Backend Imports ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import (
    init_db, record_device_session, get_device_history, get_device_stats,
    record_firmware, get_firmware_history,
    create_api_key, validate_api_key,
    log_operation, update_operation, get_operation_log,
    create_task, get_task_status,
    record_csc_lookup, get_csc_lookup_history,
    get_db_stats,
)
from backend.csc_database import CSC_DB, search_csc, get_csc, get_stats
from backend.api import api as api_v1
from device_detector import detect_device, detect_via_adb, detect_via_fastboot, detect_via_heimdall
from firmware_parser import parse_firmware_string, can_flash

# ─── App Setup ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Register API blueprint
app.register_blueprint(api_v1)

# Initialize database
init_db()

# ─── Legacy USB Detection ────────────────────────────────────────────────

def detect_usb_devices():
    """Detect Samsung USB devices via system_profiler."""
    devices = []
    try:
        result = subprocess.run(['system_profiler', 'SPUSBDataType'], capture_output=True, text=True, timeout=10)
        lines = result.stdout.split('\n')
        current = {}
        for line in lines:
            s = line.strip()
            if 'SAMSUNG' in s.upper():
                current['manufacturer'] = 'Samsung Electronics'
            if 'Product ID:' in s:
                current['product_id'] = s.split(':')[-1].strip().lstrip('0x')
            if 'Vendor ID:' in s:
                current['vendor_id'] = s.split(':')[-1].strip().lstrip('0x')
            if 'Serial Number:' in s:
                current['serial'] = s.split(':')[-1].strip()
            if 'Location ID:' in s and current.get('product_id'):
                current['location'] = s.split(':')[-1].strip()
                devices.append(current)
                current = {}
    except Exception:
        pass
    return devices


# ─── Page Routes ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    devices = detect_usb_devices()
    device_info = detect_device()
    return render_template('index.html', devices=devices, device_info=device_info)

@app.route('/device-status')
def device_status():
    return render_template('device_status.html')

@app.route('/flash-guide')
def flash_guide():
    device_info = detect_device()
    return render_template('flash_guide.html', device_info=device_info)

@app.route('/models')
def models():
    return render_template('models.html')

@app.route('/reset-wizard')
def reset_wizard():
    return render_template('reset_wizard.html')

@app.route('/firmware-table')
def firmware_table():
    return render_template('firmware_table.html')

@app.route('/safety-guide')
def safety_guide():
    return render_template('safety_guide.html')

@app.route('/removal')
def removal():
    return render_template('removal.html')

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/override')
def override():
    devices = detect_usb_devices()
    return render_template('override.html', devices=devices)

@app.route('/api-docs')
def api_docs():
    return render_template('api_docs.html')

@app.route('/device-history')
def device_history():
    return render_template('device_history.html')

@app.route('/csc-browser')
def csc_browser():
    return render_template('csc_browser.html')


# ─── Legacy API Routes (v0) ──────────────────────────────────────────────

@app.route('/api/devices')
def api_devices():
    devices = detect_usb_devices()
    for d in devices:
        modes = {'685d': 'Download Mode (Odin)', '6860': 'Android / ADB', '4ee0': 'Fastboot'}
        d['mode'] = modes.get(d.get('product_id', ''), 'Unknown')
    return jsonify({'devices': devices, 'count': len(devices)})

@app.route('/api/detect')
def api_detect():
    devices = detect_usb_devices()
    result = []
    for d in devices:
        modes = {'685d': 'Download Mode (Odin)', '6860': 'Android / ADB', '4ee0': 'Fastboot'}
        result.append({
            'model': d.get('product_id', 'unknown'),
            'vendor_id': d.get('vendor_id', ''),
            'product_id': d.get('product_id', ''),
            'serial': d.get('serial', ''),
            'mode': modes.get(d.get('product_id', ''), 'Unknown'),
            'location': d.get('location', ''),
        })
    return jsonify({'status': 'ok' if result else 'no_device', 'devices': result})

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({'status': 'error', 'message': 'No command provided'})
    cmd = data['command'].strip()
    timeout = data.get('timeout', 15)
    allowed = ['adb', 'fastboot', 'heimdall', 'thorjs', 'python3 -m samloader']
    if not any(cmd.startswith(p) for p in allowed):
        return jsonify({'status': 'error', 'message': 'Command not allowed'})
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=timeout)
        return jsonify({'status': 'ok', 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/heimdall/pit')
def api_heimdall_pit():
    try:
        result = subprocess.run(['heimdall', 'print-pit', '--no-reboot'], capture_output=True, text=True, timeout=30)
        return jsonify({'status': 'ok' if result.returncode == 0 else 'error', 'output': result.stdout, 'errors': result.stderr})
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'Heimdall not found'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/adb/getprop')
def api_adb_getprop():
    prop = request.args.get('prop', '')
    try:
        cmd = ['adb', 'shell', 'getprop', prop] if prop else ['adb', 'shell', 'getprop']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({'status': 'ok' if result.returncode == 0 else 'error', 'output': result.stdout.strip()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


# ─── App Runner ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("SFT v3.0.0 — Samsung Firmware Tool")
    print("  Backend: SQLite database initialized")
    print("  API: v1 endpoints at /api/v1/")
    print("  Pages: 10 routes")
    print("  Listening on http://0.0.0.0:5000")
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
