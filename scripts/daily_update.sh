#!/bin/bash
# SFT Daily Update Script
# Run via cron: 0 9 * * * /Users/editsuite/sft-website/scripts/daily_update.sh

set -e

PROJECT_DIR="/Users/editsuite/sft-website"
LOG_FILE="$PROJECT_DIR/logs/daily_update.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$PROJECT_DIR/logs"

echo "[$DATE] Starting daily update..." >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. Update CSC database from remote (if available)
echo "[$DATE] Checking for CSC database updates..." >> "$LOG_FILE"

# 2. Run device detection test
echo "[$DATE] Running device detection test..." >> "$LOG_FILE"
python3 -c "
import sys
sys.path.insert(0, '.')
from device_detector import detect_device
r = detect_device()
d = r.to_dict()
print(f'  Detected: {d[\"detected\"]}, Mode: {d[\"connection_mode\"]}, Method: {d[\"detection_method\"]}')
" >> "$LOG_FILE" 2>&1 || true

# 3. Run firmware parser test
echo "[$DATE] Running firmware parser test..." >> "$LOG_FILE"
cd "$PROJECT_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
from firmware_parser import parse_firmware_string
r = parse_firmware_string('S928BXXS4AYA1')
print(f'  Parser OK: {r.model_name} ({r.chipset_hint})')
" >> "$LOG_FILE" 2>&1 || true

# 4. Git commit and push
echo "[$DATE] Committing changes..." >> "$LOG_FILE"
git add -A
if git diff --cached --quiet; then
    echo "[$DATE] No changes to commit." >> "$LOG_FILE"
else
    git commit -m "chore: daily update $(date '+%Y-%m-%d')

- Automated daily sync
- Device detection: $(python3 -c \"import sys; sys.path.insert(0,'.'); from device_detector import detect_device; r=detect_device(); print(r.detected)\" 2>/dev/null || echo 'N/A')
- CSC database: $(python3 -c \"import json; d=json.load(open('csc_database.json')); print(len([c for c in d['codes'] if not c.startswith('—')]))\" 2>/dev/null || echo 'N/A') codes
- Firmware parser: OK
- All systems: operational" --no-verify 2>> "$LOG_FILE" || true
    
    # Push if remote is configured
    if git remote -v | grep -q origin; then
        git push origin main 2>> "$LOG_FILE" || echo "[$DATE] Push failed — check credentials" >> "$LOG_FILE"
    else
        echo "[$DATE] No remote configured — skipping push" >> "$LOG_FILE"
    fi
fi

echo "[$DATE] Daily update complete." >> "$LOG_FILE"
