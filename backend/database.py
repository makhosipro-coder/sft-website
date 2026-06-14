#!/usr/bin/env python3
"""
SFT Backend Database Layer
Version: 3.0.0 | Build: 20260615

SQLite database with:
- device_sessions: Track connected devices over time
- firmware_records: Store firmware file metadata and validation results
- csc_lookups: Cached CSC search history
- api_keys: Authentication keys for API access
- operation_log: Audit log for all operations
"""

import sqlite3
import os
import json
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'sft.db')


def get_db() -> sqlite3.Connection:
    """Get database connection with row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    conn.executescript("""
        -- Device connection sessions
        CREATE TABLE IF NOT EXISTS device_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT NOT NULL,
            model TEXT DEFAULT '',
            model_name TEXT DEFAULT '',
            connection_mode TEXT DEFAULT '',
            detection_method TEXT DEFAULT '',
            usb_vid TEXT DEFAULT '',
            usb_pid TEXT DEFAULT '',
            firmware_version TEXT DEFAULT '',
            csc TEXT DEFAULT '',
            chipset TEXT DEFAULT '',
            android_version TEXT DEFAULT '',
            battery_level TEXT DEFAULT '',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            connection_count INTEGER DEFAULT 1,
            raw_props TEXT DEFAULT '{}',
            UNIQUE(serial, model)
        );

        -- Firmware file records
        CREATE TABLE IF NOT EXISTS firmware_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            md5_hash TEXT DEFAULT '',
            file_type TEXT DEFAULT '',
            target_model TEXT DEFAULT '',
            firmware_string TEXT DEFAULT '',
            binary_version TEXT DEFAULT '',
            csc TEXT DEFAULT '',
            android_version TEXT DEFAULT '',
            is_valid BOOLEAN DEFAULT NULL,
            validation_result TEXT DEFAULT '{}',
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT DEFAULT 'local',
            notes TEXT DEFAULT ''
        );

        -- CSC lookup history
        CREATE TABLE IF NOT EXISTS csc_lookups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            csc_code TEXT NOT NULL,
            country TEXT DEFAULT '',
            carrier TEXT DEFAULT '',
            multi_group TEXT DEFAULT '',
            lookup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'database'
        );

        -- API keys for authentication
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL UNIQUE,
            key_prefix TEXT NOT NULL,
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP DEFAULT NULL,
            use_count INTEGER DEFAULT 0,
            rate_limit INTEGER DEFAULT 100
        );

        -- Operation audit log
        CREATE TABLE IF NOT EXISTS operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'pending',
            details TEXT DEFAULT '{}',
            device_serial TEXT DEFAULT '',
            api_key_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP DEFAULT NULL,
            duration_ms INTEGER DEFAULT 0,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
        );

        -- Background tasks
        CREATE TABLE IF NOT EXISTS background_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            payload TEXT DEFAULT '{}',
            result TEXT DEFAULT '{}',
            progress INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP DEFAULT NULL,
            completed_at TIMESTAMP DEFAULT NULL,
            priority INTEGER DEFAULT 5
        );

        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_device_sessions_serial ON device_sessions(serial);
        CREATE INDEX IF NOT EXISTS idx_device_sessions_last_seen ON device_sessions(last_seen);
        CREATE INDEX IF NOT EXISTS idx_firmware_records_filename ON firmware_records(filename);
        CREATE INDEX IF NOT EXISTS idx_firmware_records_model ON firmware_records(target_model);
        CREATE INDEX IF NOT EXISTS idx_csc_lookups_code ON csc_lookups(csc_code);
        CREATE INDEX IF NOT EXISTS idx_operation_log_created ON operation_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_operation_log_operation ON operation_log(operation);
        CREATE INDEX IF NOT EXISTS idx_background_tasks_status ON background_tasks(status);
    """)
    conn.commit()
    conn.close()


# ─── Device Session Functions ────────────────────────────────────────────

def record_device_session(device_info: dict) -> int:
    """Record or update a device session. Returns session ID."""
    conn = get_db()
    serial = device_info.get('serial', '')
    model = device_info.get('model', '')

    # Check if device already exists
    existing = conn.execute(
        "SELECT id, connection_count FROM device_sessions WHERE serial = ? AND model = ?",
        (serial, model)
    ).fetchone()

    if existing:
        # Update existing session
        conn.execute("""
            UPDATE device_sessions SET
                last_seen = CURRENT_TIMESTAMP,
                connection_count = connection_count + 1,
                firmware_version = COALESCE(?, firmware_version),
                csc = COALESCE(?, csc),
                battery_level = COALESCE(?, battery_level),
                raw_props = ?
            WHERE id = ?
        """, (
            device_info.get('firmware', ''),
            device_info.get('csc', ''),
            device_info.get('battery_level', ''),
            json.dumps(device_info.get('raw_props', {})),
            existing['id']
        ))
        session_id = existing['id']
    else:
        # Create new session
        cursor = conn.execute("""
            INSERT INTO device_sessions (serial, model, model_name, connection_mode, detection_method,
                usb_vid, usb_pid, firmware_version, csc, chipset, android_version, battery_level, raw_props)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            serial, model,
            device_info.get('model_name', ''),
            device_info.get('connection_mode', ''),
            device_info.get('detection_method', ''),
            device_info.get('usb_vid', ''),
            device_info.get('usb_pid', ''),
            device_info.get('firmware', ''),
            device_info.get('csc', ''),
            device_info.get('chipset', ''),
            device_info.get('android_version', ''),
            device_info.get('battery_level', ''),
            json.dumps(device_info.get('raw_props', {}))
        ))
        session_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return session_id


def get_device_history(limit: int = 50) -> List[Dict]:
    """Get recent device connection history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM device_sessions ORDER BY last_seen DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_stats() -> Dict:
    """Get device connection statistics."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM device_sessions").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM device_sessions WHERE date(last_seen) = date('now')"
    ).fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM device_sessions WHERE last_seen > datetime('now', '-1 hour')"
    ).fetchone()[0]

    # Most common models
    models = conn.execute("""
        SELECT model, model_name, COUNT(*) as count 
        FROM device_sessions GROUP BY model ORDER BY count DESC LIMIT 5
    """).fetchall()

    conn.close()
    return {
        'total_devices': total,
        'today_connections': today,
        'active_last_hour': active,
        'top_models': [dict(m) for m in models]
    }


# ─── Firmware Record Functions ────────────────────────────────────────────

def record_firmware(firmware_info: dict) -> int:
    """Record a firmware file. Returns record ID."""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO firmware_records (filename, filepath, file_size, md5_hash, file_type,
            target_model, firmware_string, binary_version, csc, android_version,
            is_valid, validation_result, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        firmware_info.get('filename', ''),
        firmware_info.get('filepath', ''),
        firmware_info.get('file_size', 0),
        firmware_info.get('md5_hash', ''),
        firmware_info.get('file_type', ''),
        firmware_info.get('target_model', ''),
        firmware_info.get('firmware_string', ''),
        firmware_info.get('binary_version', ''),
        firmware_info.get('csc', ''),
        firmware_info.get('android_version', ''),
        firmware_info.get('is_valid', None),
        json.dumps(firmware_info.get('validation_result', {})),
        firmware_info.get('notes', '')
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_firmware_history(limit: int = 50) -> List[Dict]:
    """Get recent firmware records."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM firmware_records ORDER BY upload_time DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── API Key Functions ────────────────────────────────────────────────────

def create_api_key(name: str = '', description: str = '', permissions: str = 'read') -> str:
    """Create a new API key. Returns the plain key (only shown once)."""
    raw_key = 'sft_' + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    conn = get_db()
    conn.execute("""
        INSERT INTO api_keys (key_hash, key_prefix, name, description, permissions)
        VALUES (?, ?, ?, ?, ?)
    """, (key_hash, key_prefix, name, description, permissions))
    conn.commit()
    conn.close()
    return raw_key


def validate_api_key(raw_key: str) -> Optional[Dict]:
    """Validate an API key. Returns key info if valid."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = get_db()
    row = conn.execute("""
        SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1
    """, (key_hash,)).fetchone()

    if row:
        # Update last used
        conn.execute("""
            UPDATE api_keys SET last_used = CURRENT_TIMESTAMP, use_count = use_count + 1
            WHERE id = ?
        """, (row['id'],))
        conn.commit()

    conn.close()
    return dict(row) if row else None


# ─── Operation Log Functions ──────────────────────────────────────────────

def log_operation(operation: str, category: str = 'general', status: str = 'pending',
                  details: dict = None, device_serial: str = '') -> int:
    """Log an operation. Returns log ID."""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO operation_log (operation, category, status, details, device_serial)
        VALUES (?, ?, ?, ?, ?)
    """, (operation, category, status, json.dumps(details or {}), device_serial))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_operation(log_id: int, status: str, details: dict = None, duration_ms: int = 0):
    """Update an operation log entry."""
    conn = get_db()
    conn.execute("""
        UPDATE operation_log SET status = ?, details = ?, duration_ms = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, json.dumps(details or {}), duration_ms, log_id))
    conn.commit()
    conn.close()


def get_operation_log(limit: int = 100, category: str = None) -> List[Dict]:
    """Get recent operation log entries."""
    conn = get_db()
    if category:
        rows = conn.execute("""
            SELECT * FROM operation_log WHERE category = ? ORDER BY created_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Background Task Functions ────────────────────────────────────────────

def create_task(task_type: str, payload: dict = None, priority: int = 5) -> int:
    """Create a background task. Returns task ID."""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO background_tasks (task_type, payload, priority)
        VALUES (?, ?, ?)
    """, (task_type, json.dumps(payload or {}), priority))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_next_task() -> Optional[Dict]:
    """Get the next queued task."""
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM background_tasks WHERE status = 'queued'
        ORDER BY priority ASC, created_at ASC LIMIT 1
    """).fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(task_id: int, status: str = None, progress: int = None,
                result: dict = None, error: str = None):
    """Update a background task."""
    conn = get_db()
    if status:
        if status == 'running':
            conn.execute("UPDATE background_tasks SET status = ?, started_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (status, task_id))
        elif status in ('completed', 'failed'):
            conn.execute("UPDATE background_tasks SET status = ?, completed_at = CURRENT_TIMESTAMP, result = ?, error = ? WHERE id = ?",
                        (status, json.dumps(result or {}), error or '', task_id))
        else:
            conn.execute("UPDATE background_tasks SET status = ? WHERE id = ?", (status, task_id))
    if progress is not None:
        conn.execute("UPDATE background_tasks SET progress = ? WHERE id = ?", (progress, task_id))
    conn.commit()
    conn.close()


def get_task_status(task_id: int) -> Optional[Dict]:
    """Get task status."""
    conn = get_db()
    row = conn.execute("SELECT * FROM background_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── CSC Lookup Functions ────────────────────────────────────────────────

def record_csc_lookup(csc_code: str, country: str = '', carrier: str = '',
                      multi_group: str = '', source: str = 'database'):
    """Record a CSC lookup."""
    conn = get_db()
    conn.execute("""
        INSERT INTO csc_lookups (csc_code, country, carrier, multi_group, source)
        VALUES (?, ?, ?, ?, ?)
    """, (csc_code, country, carrier, multi_group, source))
    conn.commit()
    conn.close()


def get_csc_lookup_history(limit: int = 50) -> List[Dict]:
    """Get CSC lookup history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM csc_lookups ORDER BY lookup_time DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Database Maintenance ────────────────────────────────────────────────

def cleanup_old_records(days: int = 30):
    """Clean up old records."""
    conn = get_db()
    conn.execute("DELETE FROM operation_log WHERE created_at < datetime('now', ?)", (f'-{days} days',))
    conn.execute("DELETE FROM background_tasks WHERE created_at < datetime('now', ?) AND status IN ('completed', 'failed')", (f'-{days} days',))
    conn.execute("DELETE FROM csc_lookups WHERE lookup_time < datetime('now', ?)", (f'-{days} days',))
    conn.commit()
    conn.close()


def get_db_stats() -> Dict:
    """Get database statistics."""
    conn = get_db()
    tables = ['device_sessions', 'firmware_records', 'csc_lookups', 'api_keys', 'operation_log', 'background_tasks']
    stats = {}
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        stats[table] = count
    conn.close()
    return stats


# ─── Init on Import ──────────────────────────────────────────────────────

init_db()
