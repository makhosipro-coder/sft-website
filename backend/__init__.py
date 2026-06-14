"""
SFT Backend Package
Version: 3.0.0
"""

from backend.database import (
    init_db, record_device_session, get_device_history, get_device_stats,
    record_firmware, get_firmware_history,
    create_api_key, validate_api_key,
    log_operation, update_operation, get_operation_log,
    create_task, get_next_task, update_task, get_task_status,
    record_csc_lookup, get_csc_lookup_history,
    cleanup_old_records, get_db_stats,
)
from backend.csc_database import CSC_DB, search_csc, get_csc, get_stats

__all__ = [
    'init_db', 'record_device_session', 'get_device_history', 'get_device_stats',
    'record_firmware', 'get_firmware_history',
    'create_api_key', 'validate_api_key',
    'log_operation', 'update_operation', 'get_operation_log',
    'create_task', 'get_next_task', 'update_task', 'get_task_status',
    'record_csc_lookup', 'get_csc_lookup_history',
    'cleanup_old_records', 'get_db_stats',
    'CSC_DB', 'search_csc', 'get_csc', 'get_stats',
]
