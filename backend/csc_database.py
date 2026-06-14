#!/usr/bin/env python3
"""
SFT CSC Database Module
Loads CSC data from csc_database.json for use in backend queries.
"""

import json
import os

_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'csc_database.json')

CSC_DB = {}
MULTI_CSC_GROUPS = {}


def load():
    """Load CSC database from JSON file."""
    global CSC_DB, MULTI_CSC_GROUPS
    try:
        with open(_db_path) as f:
            data = json.load(f)
        CSC_DB = data.get('codes', {})
        MULTI_CSC_GROUPS = data.get('multi_csc_groups', {})
    except Exception as e:
        print(f"Warning: Could not load CSC database: {e}")
        CSC_DB = {}
        MULTI_CSC_GROUPS = {}


def get_csc(code: str) -> dict:
    """Get CSC code details."""
    code = code.strip().upper()
    return CSC_DB.get(code, {})


def search_csc(query: str = '', region: str = '', limit: int = 50) -> list:
    """Search CSC database."""
    results = []
    query_upper = query.strip().upper()

    for code, info in CSC_DB.items():
        if code.startswith('——'):
            continue

        match = False
        if query_upper:
            if (query_upper in code or
                query_upper in info.get('country', '').upper() or
                query_upper in info.get('carrier', '').upper()):
                match = True
        if region and not match:
            if region.lower() in info.get('multi_group', '').lower():
                match = True
        if match or (not query_upper and not region):
            results.append({'code': code, **info})
        if len(results) >= limit:
            break

    return results


def get_stats() -> dict:
    """Get CSC database statistics."""
    total = len([c for c in CSC_DB if not c.startswith('——')])
    regions = {}
    sa_count = 0
    for code, info in CSC_DB.items():
        if code.startswith('——'):
            continue
        group = info.get('multi_group', 'Single')
        regions[group] = regions.get(group, 0) + 1
        if 'South Africa' in info.get('country', ''):
            sa_count += 1

    return {
        'total_codes': total,
        'regions': regions,
        'south_africa_codes': sa_count,
    }


# Auto-load on import
load()
