#!/usr/bin/env python3
"""SFT Launcher — runs without debug/reloader to avoid port conflicts."""
from app import app
app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
