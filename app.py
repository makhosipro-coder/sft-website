from flask import Flask, render_template, jsonify, request
import subprocess
import os
import re
import json

app = Flask(__name__)

# ─── Import Device Detector ─────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))
from device_detector import (
    detect_device,
    detect_via_adb,
    detect_via_fastboot,
    detect_via_heimdall,
    detect_via_usb_descriptor,
    KNOWN_MODEL_PIDS,
)

# ─── USB Device Detection (legacy fallback) ──────────────────────────────

def detect_usb_devices():
    """Detect connected Samsung USB devices via system_profiler."""
    devices = []
    try:
        result = subprocess.run(
            ['system_profiler', 'SPUSBDataType'],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.split('\n')
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
                devices.append(current)
                current = {}
    except Exception:
        pass
    return devices

def get_device_mode(pid):
    """Map USB Product ID to device mode."""
    modes = {
        '685d': 'Download Mode (Odin)',
        '6860': 'Android / ADB',
        '4ee0': 'Fastboot',
    }
    return modes.get(pid, 'Unknown')

# ─── Page Routes ────────────────────────────────────────────────────────

@app.route('/')
def index():
    devices = detect_usb_devices()
    device_info = detect_device()
    return render_template('index.html', devices=devices, device_info=device_info)

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

@app.route('/about')
def about():
    return render_template('coming_soon.html', page_name='About',
                          message='Project details and contributor information coming soon.')

# ─── API Routes ─────────────────────────────────────────────────────────

@app.route('/api/devices')
def api_devices():
    """Return detected USB devices as JSON."""
    devices = detect_usb_devices()
    for d in devices:
        d['mode'] = get_device_mode(d.get('product_id', ''))
    return jsonify({'devices': devices, 'count': len(devices)})

@app.route('/api/detect')
def api_detect():
    """Run full device detection and return detailed info."""
    devices = detect_usb_devices()
    result = []
    for d in devices:
        mode = get_device_mode(d.get('product_id', ''))
        info = {
            'model': d.get('product_id', 'unknown'),
            'vendor_id': d.get('vendor_id', ''),
            'product_id': d.get('product_id', ''),
            'serial': d.get('serial', ''),
            'mode': mode,
            'location': d.get('location', ''),
        }
        result.append(info)
    return jsonify({'status': 'ok' if result else 'no_device', 'devices': result})

@app.route('/api/command', methods=['POST'])
def api_command():
    """Execute a command on the connected device."""
    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({'status': 'error', 'message': 'No command provided'})
    
    cmd = data['command'].strip()
    timeout = data.get('timeout', 15)
    
    # Whitelist of allowed commands
    allowed_prefixes = ['adb', 'fastboot', 'heimdall', 'thorjs', 'python3 -m samloader']
    if not any(cmd.startswith(p) for p in allowed_prefixes):
        return jsonify({'status': 'error', 'message': 'Command not allowed'})
    
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True, text=True, timeout=timeout
        )
        return jsonify({
            'status': 'ok',
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Command timed out'})
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'Command not found. Is the tool installed?'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/heimdall/pit')
def api_heimdall_pit():
    """Read PIT via Heimdall."""
    try:
        result = subprocess.run(
            ['heimdall', 'print-pit', '--no-reboot'],
            capture_output=True, text=True, timeout=30
        )
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'errors': result.stderr,
        })
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'Heimdall not found. Install via: brew install heimdall'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/adb/getprop')
def api_adb_getprop():
    """Get device properties via ADB."""
    prop = request.args.get('prop', '')
    try:
        if prop:
            cmd = ['adb', 'shell', 'getprop', prop]
        else:
            cmd = ['adb', 'shell', 'getprop']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': result.stdout.strip(),
        })
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'ADB not found'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/device-status')
def device_status():
    """Live device status page."""
    return render_template('device_status.html')

@app.route('/flash-guide')
def flash_guide():
    """Guided Odin flash workflow."""
    device_info = detect_device()
    return render_template('flash_guide.html', device_info=device_info)

# ─── Auto-Detection API ─────────────────────────────────────────────────

@app.route('/api/device/detect')
def api_device_detect():
    """Full auto-detect: tries ADB → Fastboot → Heimdall → USB."""
    info = detect_device()
    return jsonify(info.to_dict())

@app.route('/api/device/adb')
def api_device_adb():
    """Detect via ADB only."""
    info = detect_via_adb()
    return jsonify(info.to_dict() if info else {'detected': False})

@app.route('/api/device/fastboot')
def api_device_fastboot():
    """Detect via Fastboot only."""
    info = detect_via_fastboot()
    return jsonify(info.to_dict() if info else {'detected': False})

@app.route('/api/device/heimdall')
def api_device_heimdall():
    """Detect via Heimdall (Download Mode) only."""
    info = detect_via_heimdall()
    return jsonify(info.to_dict() if info else {'detected': False})

@app.route('/api/device/status')
def api_device_status():
    """Quick check: is a Samsung device connected? Returns minimal info."""
    info = detect_device()
    return jsonify({
        'connected': info.detected,
        'model': info.model,
        'model_name': info.model_name,
        'connection_mode': info.connection_mode,
        'firmware': info.firmware,
        'csc': info.csc,
        'detection_method': info.detection_method,
    })

@app.route('/api/device/models')
def api_device_models():
    """Return list of known Samsung models."""
    return jsonify({'models': KNOWN_MODEL_PIDS})

@app.route('/api/firmware/validate', methods=['POST'])
def api_firmware_validate():
    """Validate a firmware file (tar.md5 integrity check)."""
    data = request.get_json()
    if not data or 'filepath' not in data:
        return jsonify({'status': 'error', 'message': 'No filepath provided'})

    filepath = data['filepath']
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': f'File not found: {filepath}'})

    result = {'filepath': filepath, 'filename': os.path.basename(filepath)}

    # Check file size
    file_size = os.path.getsize(filepath)
    result['size_bytes'] = file_size
    result['size_human'] = _format_size(file_size)

    # Check if it's a tar.md5 file
    if filepath.endswith('.tar.md5'):
        result['type'] = 'tar.md5'
        # Verify MD5
        stdout, stderr, rc = _run_cmd(['md5', '-q', filepath], timeout=30)
        if rc == 0:
            result['md5'] = stdout.strip()
        # Try to list tar contents
        stdout, stderr, rc = _run_cmd(['tar', 'tf', filepath], timeout=30)
        if rc == 0:
            files = [f for f in stdout.split('\n') if f.strip()]
            result['tar_contents'] = files
            result['tar_file_count'] = len(files)
            result['valid'] = True
        else:
            result['valid'] = False
            result['error'] = stderr
    elif filepath.endswith('.tar'):
        result['type'] = 'tar'
        stdout, stderr, rc = _run_cmd(['tar', 'tf', filepath], timeout=30)
        if rc == 0:
            files = [f for f in stdout.split('\n') if f.strip()]
            result['tar_contents'] = files
            result['tar_file_count'] = len(files)
            result['valid'] = True
        else:
            result['valid'] = False
            result['error'] = stderr
    else:
        result['type'] = 'unknown'
        result['valid'] = None
        result['warning'] = 'Unknown file type. Expected .tar.md5 or .tar'

    return jsonify(result)

def _format_size(size_bytes):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
