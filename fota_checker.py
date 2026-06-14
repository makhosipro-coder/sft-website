#!/usr/bin/env python3
"""
Samsung FOTA Firmware Checker
Version: 1.0.0 | Build: 20260615

Queries Samsung's FOTA (Firmware Over-The-Air) server to check
the latest available firmware for a given model and CSC.

FOTA URL format:
  https://fota-cloud-dn.ospserver.net/firmware/{CSC}/{MODEL}/version.xml

Also supports:
  - version.test.xml (test builds)
  - list.xml (firmware list)
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import sys
import re
from typing import Optional


FOTA_BASE_URL = "https://fota-cloud-dn.ospserver.net/firmware"


class FotaResult:
    """Result from a FOTA query."""

    def __init__(self):
        self.model: str = ""
        self.csc: str = ""
        self.latest_firmware: str = ""
        self.current_version: str = ""
        self.binary_version: str = ""
        self.android_version: str = ""
        self.security_patch: str = ""
        self.release_date: str = ""
        self.file_size: str = ""
        self.download_url: str = ""
        self.changelog: str = ""
        self.is_update_available: bool = False
        self.error: Optional[str] = None
        self.raw_xml: str = ""

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "csc": self.csc,
            "latest_firmware": self.latest_firmware,
            "current_version": self.current_version,
            "binary_version": self.binary_version,
            "android_version": self.android_version,
            "security_patch": self.security_patch,
            "release_date": self.release_date,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "is_update_available": self.is_update_available,
            "error": self.error,
        }


def query_fota(model: str, csc: str, timeout: int = 15) -> FotaResult:
    """
    Query Samsung's FOTA server for the latest firmware.

    Args:
        model: Device model (e.g., "SM-S928B")
        csc: CSC code (e.g., "OXM")
        timeout: Request timeout in seconds

    Returns:
        FotaResult with parsed firmware information
    """
    result = FotaResult()
    result.model = model
    result.csc = csc

    url = f"{FOTA_BASE_URL}/{csc}/{model}/version.xml"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Samsung FOTA Client",
            "Accept": "application/xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            result.raw_xml = data
            _parse_fota_xml(data, result)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            result.error = f"No firmware found for {model} with CSC {csc}. Check model/CSC."
        else:
            result.error = f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        result.error = f"Connection failed: {e.reason}"
    except Exception as e:
        result.error = f"Error: {str(e)}"

    return result


def _parse_fota_xml(xml_data: str, result: FotaResult):
    """Parse FOTA XML response."""
    try:
        root = ET.fromstring(xml_data)

        # FOTA XML structure varies, but common elements:
        for elem in root.iter():
            tag = elem.tag.lower()
            text = elem.text.strip() if elem.text else ""

            if not text:
                continue

            if tag in ("firmware", "fw_ver", "version"):
                if not result.latest_firmware:
                    result.latest_firmware = text
            elif tag in ("model", "device"):
                if not result.model:
                    result.model = text
            elif tag in ("csc", "sales_code"):
                if not result.csc:
                    result.csc = text
            elif tag in ("binary", "binary_version", "bl_version"):
                result.binary_version = text
            elif tag in ("android_version", "android_ver", "os_version"):
                result.android_version = text
            elif tag in ("security_patch", "security_patch_level", "spl"):
                result.security_patch = text
            elif tag in ("release_date", "date", "build_date"):
                result.release_date = text
            elif tag in ("file_size", "size"):
                result.file_size = text
            elif tag in ("download_url", "url", "fota_url"):
                result.download_url = text
            elif tag in ("changelog", "change_log", "notes"):
                result.changelog = text

        # If we got a firmware string but no binary version, try to extract it
        if result.latest_firmware and not result.binary_version:
            # Extract binary version from firmware string (char 9)
            fw = result.latest_firmware
            if len(fw) >= 9:
                result.binary_version = fw[8]

    except ET.ParseError as e:
        result.error = f"XML parse error: {e}"


def query_fota_list(model: str, csc: str, timeout: int = 15) -> list:
    """
    Query the FOTA server for a list of available firmware versions.

    Returns a list of firmware version strings.
    """
    url = f"{FOTA_BASE_URL}/{csc}/{model}/list.xml"
    versions = []

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Samsung FOTA Client",
            "Accept": "application/xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            root = ET.fromstring(data)
            for elem in root.iter():
                text = elem.text.strip() if elem.text else ""
                if text and len(text) == 13 and text[0].isalpha():
                    versions.append(text)
    except Exception:
        pass

    return versions


def check_firmware_update(model: str, csc: str, current_fw: str) -> dict:
    """
    Check if a firmware update is available.

    Returns a dict with update info and comparison.
    """
    result = query_fota(model, csc)

    if result.error:
        return {
            "status": "error",
            "error": result.error,
            "model": model,
            "csc": csc,
        }

    # Compare firmware strings
    latest = result.latest_firmware
    current = current_fw.strip().upper()

    update_info = {
        "status": "ok",
        "model": model,
        "csc": csc,
        "current_firmware": current,
        "latest_firmware": latest,
        "is_update_available": False,
        "binary_comparison": "",
        "android_version": result.android_version,
        "security_patch": result.security_patch,
        "release_date": result.release_date,
    }

    if latest and current:
        if latest.upper() == current.upper():
            update_info["is_update_available"] = False
            update_info["binary_comparison"] = "You are on the latest firmware."
        else:
            # Compare binary versions
            if len(latest) >= 9 and len(current) >= 9:
                latest_bl = latest[8]
                current_bl = current[8]

                # Convert to numeric for comparison
                def bl_to_int(c):
                    if c.isdigit():
                        return int(c)
                    return ord(c.upper()) - ord('A') + 10

                latest_bl_int = bl_to_int(latest_bl)
                current_bl_int = bl_to_int(current_bl)

                if latest_bl_int > current_bl_int:
                    update_info["is_update_available"] = True
                    update_info["binary_comparison"] = (
                        f"UPDATE AVAILABLE: Bootloader v{current_bl} → v{latest_bl}. "
                        f"This is a ONE-WAY upgrade."
                    )
                elif latest_bl_int == current_bl_int:
                    update_info["is_update_available"] = True
                    update_info["binary_comparison"] = (
                        f"UPDATE AVAILABLE: Same bootloader version v{current_bl}. "
                        f"Security patch or minor update."
                    )
                else:
                    update_info["is_update_available"] = False
                    update_info["binary_comparison"] = (
                        f"Your firmware has a HIGHER bootloader version than the "
                        f"latest available. You may be on a beta or regional build."
                    )
            else:
                update_info["is_update_available"] = True
                update_info["binary_comparison"] = "Firmware update available (version comparison unavailable)."

    return update_info


def format_fota_result(result: FotaResult) -> str:
    """Format a FOTA result as a human-readable string."""
    if result.error:
        return f"ERROR: {result.error}"

    lines = [
        f"═══════════════════════════════════════════════════",
        f"  SAMSUNG FOTA FIRMWARE CHECK",
        f"═══════════════════════════════════════════════════",
        f"",
        f"  Model:     {result.model}",
        f"  CSC:       {result.csc}",
        f"",
        f"  Latest Firmware:  {result.latest_firmware or 'N/A'}",
        f"  Binary Version:   {result.binary_version or 'N/A'}",
        f"  Android Version:  {result.android_version or 'N/A'}",
        f"  Security Patch:   {result.security_patch or 'N/A'}",
        f"  Release Date:     {result.release_date or 'N/A'}",
        f"  File Size:        {result.file_size or 'N/A'}",
        f"",
    ]

    if result.download_url:
        lines.append(f"  Download URL: {result.download_url}")
        lines.append("")

    lines.append(f"═══════════════════════════════════════════════════")
    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Samsung FOTA Firmware Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s SM-S928B OXM
  %(prog)s SM-A042F XSG --check A042FXXSFEZB9
  %(prog)s SM-S928B OXM --json
        """
    )
    parser.add_argument("model", help="Device model (e.g., SM-S928B)")
    parser.add_argument("csc", help="CSC code (e.g., OXM, XAA, INS)")
    parser.add_argument("--check", metavar="CURRENT_FW",
                        help="Check if update is available for current firmware")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--list", action="store_true", help="List available firmware versions")

    args = parser.parse_args()

    if args.list:
        versions = query_fota_list(args.model, args.csc)
        if versions:
            print(f"\n  Available firmware for {args.model} ({args.csc}):")
            for v in versions:
                print(f"    {v}")
            print()
        else:
            print(f"\n  No firmware list available for {args.model} ({args.csc})\n")
        return

    if args.check:
        result = check_firmware_update(args.model, args.csc, args.check)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status = "UPDATE AVAILABLE" if result.get("is_update_available") else "UP TO DATE"
            print(f"\n  Status: {status}")
            print(f"  Current:  {result['current_firmware']}")
            print(f"  Latest:   {result['latest_firmware']}")
            print(f"  {result.get('binary_comparison', '')}")
            if result.get("android_version"):
                print(f"  Android:  {result['android_version']}")
            if result.get("security_patch"):
                print(f"  Security: {result['security_patch']}")
            print()
        return

    result = query_fota(args.model, args.csc)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_fota_result(result))


if __name__ == "__main__":
    main()
