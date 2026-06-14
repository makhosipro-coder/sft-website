#!/usr/bin/env python3
"""
SFT Backend API v1
Version: 3.0.0 | Build: 20260615

REST API with:
- API key authentication
- Rate limiting
- Proper error handling
- Pagination
- Device session tracking
- Firmware management
- Background task queue
"""

import os
import sys
import time
import json
import threading
from functools import wraps
from flask import Blueprint, request, jsonify, g

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import (
    record_device_session, get_device_history, get_device_stats,
    record_firmware, get_firmware_history,
    create_api_key, validate_api_key,
    log_operation, update_operation, get_operation_log,
    create_task, get_next_task, update_task, get_task_status,
    record_csc_lookup, get_csc_lookup_history,
    cleanup_old_records, get_db_stats,
)
from device_detector import detect_device
from firmware_parser import parse_firmware_string, can_flash
from backend.csc_database import CSC_DB, search_csc, get_csc, get_stats

api = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# ─── Rate Limiting ────────────────────────────────────────────────────────

_rate_limits = {}


def check_rate_limit(key: str, limit: int = 100) -> bool:
    """Simple in-memory rate limiter."""
    now = time.time()
    window = 3600  # 1 hour
    if key not in _rate_limits:
        _rate_limits[key] = []
    # Clean old entries
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= limit:
        return False
    _rate_limits[key].append(now)
    return True


# ─── Authentication ───────────────────────────────────────────────────────

def require_auth(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            # Allow read-only without auth for public endpoints
            if request.method == 'GET' and not request.path.startswith('/api/v1/admin'):
                g.api_key = None
                return f(*args, **kwargs)
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header[7:]
        key_info = validate_api_key(token)
        if not key_info:
            return jsonify({'error': 'Invalid or expired API key'}), 401

        if not check_rate_limit(key_info['key_prefix'], key_info.get('rate_limit', 100)):
            return jsonify({'error': 'Rate limit exceeded'}), 429

        g.api_key = key_info
        return f(*args, **kwargs)
    return decorated


def require_write(f):
    """Decorator to require write permissions."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.get('api_key'):
            return jsonify({'error': 'Authentication required for write operations'}), 401
        if g.api_key.get('permissions') not in ('write', 'admin'):
            return jsonify({'error': 'Write permission required'}), 403
        return f(*args, **kwargs)
    return decorated


# ─── Error Handlers ───────────────────────────────────────────────────────

@api.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found', 'path': request.path}), 404


@api.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ─── Device Endpoints ────────────────────────────────────────────────────

@api.route('/devices/detect', methods=['GET'])
@require_auth
def devices_detect():
    """Full device auto-detection."""
    start = time.time()
    api_key_id = g.get('api_key', {}).get('id') if g.get('api_key') else None
    log_id = log_operation('device_detect', 'device', 'running')

    try:
        result = detect_device()
        d = result.to_dict()

        if d.get('detected'):
            try:
                record_device_session(d)
                if d.get('csc'):
                    record_csc_lookup(d['csc'], source='auto-detect')
            except Exception:
                pass  # Don't fail detection if DB write fails

        duration = int((time.time() - start) * 1000)
        update_operation(log_id, 'completed', {'detected': d.get('detected')}, duration)

        return jsonify({
            'status': 'ok',
            'data': d,
            'duration_ms': duration,
        })
    except Exception as e:
        update_operation(log_id, 'failed', {'error': str(e)})
        return jsonify({'status': 'error', 'message': str(e)}), 500


@api.route('/devices/history', methods=['GET'])
@require_auth
def devices_history():
    """Get device connection history."""
    limit = request.args.get('limit', 50, type=int)
    history = get_device_history(limit=limit)
    return jsonify({'status': 'ok', 'data': history, 'count': len(history)})


@api.route('/devices/stats', methods=['GET'])
@require_auth
def devices_stats():
    """Get device connection statistics."""
    stats = get_device_stats()
    return jsonify({'status': 'ok', 'data': stats})


@api.route('/devices/session/<serial>', methods=['GET'])
@require_auth
def device_session(serial):
    """Get details for a specific device session."""
    history = get_device_history(limit=100)
    device = next((d for d in history if d.get('serial') == serial), None)
    if not device:
        return jsonify({'status': 'error', 'message': 'Device not found'}), 404
    return jsonify({'status': 'ok', 'data': device})


# ─── Firmware Endpoints ───────────────────────────────────────────────────

@api.route('/firmware/parse', methods=['POST'])
@require_auth
def firmware_parse():
    """Parse a firmware string."""
    data = request.get_json()
    if not data or 'firmware' not in data:
        return jsonify({'error': 'Missing firmware string'}), 400

    fw_string = data['firmware'].strip().upper()
    result = parse_firmware_string(fw_string)

    if not result.valid:
        return jsonify({'status': 'error', 'message': result.error}), 400

    d = {
        'raw': result.raw, 'valid': result.valid,
        'hardware': result.hardware, 'model': result.model_name,
        'variant': result.variant_name, 'market': result.market,
        'csc_group': result.csc_group, 'binary_version': result.binary_version,
        'type': result.type_name, 'year': result.year,
        'month': result.month_name, 'chipset': result.chipset_hint,
        'is_mediatek': result.is_mediatek, 'android': result.android_version,
    }
    return jsonify({'status': 'ok', 'data': d})


@api.route('/firmware/check', methods=['POST'])
@require_auth
def firmware_check():
    """Rollback prevention check between two firmware strings."""
    data = request.get_json()
    if not data or 'target' not in data or 'current' not in data:
        return jsonify({'error': 'Missing target and/or current firmware strings'}), 400

    result = can_flash(data['target'].strip().upper(), data['current'].strip().upper())
    return jsonify({'status': 'ok', 'data': result})


@api.route('/firmware/validate', methods=['POST'])
@require_auth
@require_write
def firmware_validate():
    """Validate a firmware file (tar.md5 integrity check)."""
    data = request.get_json()
    if not data or 'filepath' not in data:
        return jsonify({'error': 'Missing filepath'}), 400

    filepath = data['filepath']
    if not os.path.exists(filepath):
        return jsonify({'error': f'File not found: {filepath}'}), 404

    start = time.time()
    result = {'filepath': filepath, 'filename': os.path.basename(filepath)}

    file_size = os.path.getsize(filepath)
    result['file_size'] = file_size
    result['file_size_human'] = _format_size(file_size)

    if filepath.endswith('.tar.md5') or filepath.endswith('.tar'):
        result['type'] = 'tar.md5' if filepath.endswith('.tar.md5') else 'tar'
        # MD5 hash
        import subprocess
        md5_result = subprocess.run(['md5', '-q', filepath], capture_output=True, text=True, timeout=60)
        if md5_result.returncode == 0:
            result['md5'] = md5_result.stdout.strip()

        # List contents
        tar_result = subprocess.run(['tar', 'tf', filepath], capture_output=True, text=True, timeout=60)
        if tar_result.returncode == 0:
            files = [f for f in tar_result.stdout.split('\n') if f.strip()]
            result['contents'] = files
            result['file_count'] = len(files)
            result['valid'] = True
        else:
            result['valid'] = False
            result['error'] = tar_result.stderr.strip()
    else:
        result['type'] = 'unknown'
        result['valid'] = None

    # Record in database
    record_firmware({
        'filename': result['filename'],
        'filepath': filepath,
        'file_size': file_size,
        'md5_hash': result.get('md5', ''),
        'file_type': result.get('type', ''),
        'is_valid': result.get('valid'),
        'validation_result': result,
    })

    result['duration_ms'] = int((time.time() - start) * 1000)
    return jsonify({'status': 'ok', 'data': result})


@api.route('/firmware/history', methods=['GET'])
@require_auth
def firmware_history():
    """Get firmware validation history."""
    limit = request.args.get('limit', 50, type=int)
    history = get_firmware_history(limit=limit)
    return jsonify({'status': 'ok', 'data': history, 'count': len(history)})


# ─── CSC Endpoints ────────────────────────────────────────────────────────

@api.route('/csc/search', methods=['GET'])
@require_auth
def csc_search():
    """Search CSC database."""
    query = request.args.get('q', '').strip().upper()
    region = request.args.get('region', '').strip()
    limit = request.args.get('limit', 50, type=int)

    results = []
    for code, info in CSC_DB.items():
        if code.startswith('——'):
            continue
        match = False
        if query:
            if (query in code or
                query in info.get('country', '').upper() or
                query in info.get('carrier', '').upper()):
                match = True
        if region and not match:
            if region.lower() in info.get('multi_group', '').lower():
                match = True
        if match or (not query and not region):
            results.append({'code': code, **info})
        if len(results) >= limit:
            break

    # Record lookups
    if query:
        record_csc_lookup(query, source='api_search')

    return jsonify({'status': 'ok', 'data': results, 'count': len(results)})


@api.route('/csc/<code>', methods=['GET'])
@require_auth
def csc_detail(code):
    """Get CSC code details."""
    code = code.strip().upper()
    if code in CSC_DB and not code.startswith('——'):
        record_csc_lookup(code, source='api_detail')
        return jsonify({'status': 'ok', 'data': {'code': code, **CSC_DB[code]}})
    return jsonify({'status': 'error', 'message': f'CSC code not found: {code}'}), 404


@api.route('/csc/stats', methods=['GET'])
@require_auth
def csc_stats():
    """Get CSC database statistics."""
    total = len([c for c in CSC_DB if not c.startswith('——')])
    regions = {}
    sa_count = 0
    for code, info in CSC_DB.items():
        if code.startswith('——') or not isinstance(info, dict):
            continue
        group = info.get('multi_group') or 'Single'
        regions[group] = regions.get(group, 0) + 1
        if 'South Africa' in info.get('country', ''):
            sa_count += 1

    return jsonify({
        'status': 'ok',
        'data': {
            'total_codes': total,
            'regions': regions,
            'south_africa_codes': sa_count,
        }
    })


# ─── Task Endpoints ───────────────────────────────────────────────────────

@api.route('/tasks', methods=['POST'])
@require_auth
@require_write
def create_task_endpoint():
    """Create a background task."""
    data = request.get_json()
    if not data or 'type' not in data:
        return jsonify({'error': 'Missing task type'}), 400

    task_id = create_task(
        task_type=data['type'],
        payload=data.get('payload', {}),
        priority=data.get('priority', 5)
    )

    return jsonify({'status': 'ok', 'data': {'task_id': task_id, 'status': 'queued'}}), 201


@api.route('/tasks/<int:task_id>', methods=['GET'])
@require_auth
def get_task(task_id):
    """Get task status."""
    task = get_task_status(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'status': 'ok', 'data': task})


# ─── Admin Endpoints ──────────────────────────────────────────────────────

@api.route('/admin/stats', methods=['GET'])
@require_auth
def admin_stats():
    """Get system statistics."""
    db_stats = get_db_stats()
    op_log = get_operation_log(limit=5)

    return jsonify({
        'status': 'ok',
        'data': {
            'database': db_stats,
            'recent_operations': op_log,
            'uptime': 'running',
        }
    })


@api.route('/admin/keys', methods=['POST'])
@require_auth
@require_write
def admin_create_key():
    """Create a new API key."""
    data = request.get_json() or {}
    name = data.get('name', '')
    description = data.get('description', '')
    permissions = data.get('permissions', 'read')

    if permissions not in ('read', 'write', 'admin'):
        return jsonify({'error': 'Invalid permissions. Use: read, write, admin'}), 400

    raw_key = create_api_key(name, description, permissions)
    return jsonify({
        'status': 'ok',
        'data': {
            'key': raw_key,
            'name': name,
            'permissions': permissions,
            'warning': 'Store this key safely. It cannot be retrieved again.',
        }
    }), 201


@api.route('/admin/cleanup', methods=['POST'])
@require_auth
@require_write
def admin_cleanup():
    """Clean up old records."""
    data = request.get_json() or {}
    days = data.get('days', 30)
    cleanup_old_records(days)
    return jsonify({'status': 'ok', 'message': f'Cleaned up records older than {days} days'})


# ─── Health Check ─────────────────────────────────────────────────────────

@api.route('/health', methods=['GET'])
def health_check():
    """Public health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'SFT Backend API',
        'version': '3.0.0',
        'timestamp': time.time(),
    })


# ─── Helpers ──────────────────────────────────────────────────────────────

def _format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'
