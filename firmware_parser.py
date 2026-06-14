#!/usr/bin/env python3
"""
Samsung Firmware String Parser Engine
Version: 1.1.0 | Build: 20260615

Parses 13-character Samsung firmware strings into component parts.
"""

import re
import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional


SERIES_CODES = {
    "S": "Galaxy S", "N": "Galaxy Note", "A": "Galaxy A", "M": "Galaxy M",
    "F": "Galaxy F", "Z": "Galaxy Z", "J": "Galaxy J", "T": "Galaxy Tab",
    "R": "Galaxy R", "G": "Galaxy Grand", "E": "Galaxy E", "X": "Galaxy Xcover",
    "C": "Galaxy C", "W": "Galaxy W", "Q": "Galaxy Q", "V": "Galaxy V",
    "K": "Galaxy K", "B": "Galaxy B", "U": "Galaxy U",
}

MODEL_NUMBERS = {
    "928": "S24 Ultra", "926": "S24+", "921": "S24",
    "918": "S23 Ultra", "916": "S23+", "911": "S23",
    "908": "S22 Ultra", "906": "S22+", "901": "S22",
    "888": "S20 Ultra", "865": "S10+", "860": "S10", "855": "S10e",
    "845": "S9+", "835": "S9", "750": "S8+", "730": "S8",
    "986": "Note 20 Ultra", "981": "Note 20",
    "975": "Note 10+", "970": "Note 10", "960": "Note 9", "950": "Note 8",
    "946": "Z Fold 5", "936": "Z Fold 4", "731": "Z Flip 5", "721": "Z Flip 4",
    "556": "A55 5G", "546": "A54 5G", "536": "A53 5G",
    "356": "A35 5G", "346": "A34", "336": "A33 5G", "326": "A32",
    "266": "A26", "256": "A25", "246": "A24", "236": "A23",
    "166": "A16", "156": "A15", "146": "A14", "136": "A13",
    "055": "A05", "045": "A04", "042": "A04e", "035": "A03",
    "025": "A02", "015": "A01",
    "546": "M54 5G", "336": "M33 5G", "236": "M23 5G",
    "900": "Tab S9 Ultra", "800": "Tab S8 Ultra", "610": "Tab S6",
    "290": "Tab A9+", "280": "Tab A9",
}

VARIANT_CODES = {
    "B": "International/Europe", "U": "USA", "N": "Korea", "F": "China",
    "W": "Canada", "V": "Verizon", "T": "T-Mobile", "P": "Sprint",
    "M": "Latin America", "D": "Taiwan", "C": "China Carrier",
    "H": "Hong Kong", "Z": "New Zealand", "A": "Australia", "I": "India",
    "E": "Europe", "G": "Global", "L": "AT&T", "R": "US Cellular",
}

TYPE_CODES = {
    "S": "Security Update", "U": "Major Update", "C": "Critical Patch",
    "N": "Minor Update", "B": "Bug Fix", "A": "Annual Update",
    "T": "Test Build", "E": "Engineering Build", "D": "Developer Preview",
    "P": "Public Beta", "R": "Release Candidate", "V": "Vendor Update",
    "M": "Maintenance", "F": "Feature Drop", "X": "Emergency Patch",
    "Y": "Yearly Update", "Z": "Hotfix", "J": "Bootloader Update",
    "K": "Kernel Update", "W": "Warranty Update",
}

MONTH_CODES = {
    "A": "January", "B": "February", "C": "March", "D": "April",
    "E": "May", "F": "June", "G": "July", "H": "August",
    "I": "September", "J": "October", "K": "November", "L": "December",
}

MULTI_CSC_GROUPS = {
    "OXM": {"name": "Europe Multi-CSC", "region": "Europe/International", "count": 80},
    "OWO": {"name": "Latin America Multi-CSC", "region": "Latin America", "count": 40},
    "OXX": {"name": "Asia/Pacific Multi-CSC", "region": "Asia/Pacific", "count": 30},
    "OXE": {"name": "Southeast Asia Multi-CSC", "region": "Southeast Asia", "count": 15},
    "OYM": {"name": "Middle East & Africa Multi-CSC", "region": "Middle East & Africa", "count": 25},
    "OXA": {"name": "Australia/NZ Multi-CSC", "region": "Australia/New Zealand", "count": 5},
}

MEDIATEK_MODELS = {"042", "035", "025", "015", "045", "055", "135", "127", "136", "146", "156", "166", "236", "225", "326", "500", "336"}


@dataclass
class FirmwareParseResult:
    raw: str
    valid: bool
    error: Optional[str]
    hardware: str
    series_code: str
    series_name: str
    model_number: str
    model_name: str
    variant_code: str
    variant_name: str
    market: str
    csc_group: str
    csc_region: str
    csc_country_count: int
    is_multi_csc: bool
    binary_version: str
    binary_version_int: int
    type_code: str
    type_name: str
    year_code: str
    year: int
    month_code: str
    month_name: str
    build_sequence: str
    sub_revision: str
    android_version: str
    chipset_hint: str
    is_mediatek: bool
    csc: str


def _char_to_int(c):
    if c.isdigit():
        return int(c)
    return ord(c.upper()) - ord('A') + 10


def parse_firmware_string(fw_string):
    raw = fw_string.strip().upper()
    if len(raw) != 13:
        return FirmwareParseResult(
            raw=raw, valid=False, error=f"Invalid length: {len(raw)} chars (expected 13)",
            hardware="", series_code="", series_name="", model_number="", model_name="",
            variant_code="", variant_name="", market="", csc_group="", csc_region="",
            csc_country_count=0, is_multi_csc=False, binary_version="", binary_version_int=0,
            type_code="", type_name="", year_code="", year=0, month_code="", month_name="",
            build_sequence="", sub_revision="", android_version="", chipset_hint="",
            is_mediatek=False, csc="",
        )

    hw = raw[0:5]
    series_code = hw[0]
    series_name = SERIES_CODES.get(series_code, f"Unknown ({series_code})")
    model_number = hw[1:4]
    model_name = MODEL_NUMBERS.get(model_number, f"Unknown ({model_number})")
    variant_code = hw[4]
    variant_name = VARIANT_CODES.get(variant_code, f"Unknown ({variant_code})")

    market = raw[5:8]
    is_multi_csc = market in MULTI_CSC_GROUPS
    if is_multi_csc:
        group = MULTI_CSC_GROUPS[market]
        csc_group = group["name"]
        csc_region = group["region"]
        csc_country_count = group["count"]
    else:
        csc_group = f"Single CSC ({market})"
        csc_region = "Specific carrier/region"
        csc_country_count = 1

    binary_version = raw[8]
    binary_version_int = _char_to_int(binary_version)
    type_code = raw[9]
    type_name = TYPE_CODES.get(type_code, f"Unknown ({type_code})")
    year_code = raw[9]
    year = 2024 + (ord(year_code) - ord('A'))
    month_code = raw[10]
    month_name = MONTH_CODES.get(month_code, f"Unknown ({month_code})")
    build_sequence = raw[11]
    sub_revision = raw[12]
    is_mediatek = model_number in MEDIATEK_MODELS
    chipset_hint = "MediaTek" if is_mediatek else ("Snapdragon" if variant_code in ("U", "V", "T", "P", "L", "W") else "Exynos")
    android_version = f"1{year - 2020}" if year >= 2024 else "14"
    csc = market

    return FirmwareParseResult(
        raw=raw, valid=True, error=None,
        hardware=hw, series_code=series_code, series_name=series_name,
        model_number=model_number, model_name=model_name,
        variant_code=variant_code, variant_name=variant_name,
        market=market, csc_group=csc_group, csc_region=csc_region,
        csc_country_count=csc_country_count, is_multi_csc=is_multi_csc,
        binary_version=binary_version, binary_version_int=binary_version_int,
        type_code=type_code, type_name=type_name,
        year_code=year_code, year=year,
        month_code=month_code, month_name=month_name,
        build_sequence=build_sequence, sub_revision=sub_revision,
        android_version=android_version, chipset_hint=chipset_hint,
        is_mediatek=is_mediatek, csc=csc,
    )


def can_flash(target_fw, current_fw):
    target = parse_firmware_string(target_fw)
    current = parse_firmware_string(current_fw)
    result = {
        "allowed": False, "reason": "",
        "target_bl": target.binary_version_int, "current_bl": current.binary_version_int,
        "hardware_match": target.hardware == current.hardware,
        "chipset_match": target.is_mediatek == current.is_mediatek,
    }
    if not target.valid:
        result["reason"] = f"Invalid target: {target.error}"
        return result
    if not current.valid:
        result["reason"] = f"Invalid current: {current.error}"
        return result
    if not result["hardware_match"]:
        result["reason"] = f"HARDWARE MISMATCH: {target.hardware} vs {current.hardware}"
        return result
    if not result["chipset_match"]:
        result["reason"] = f"CHIPSET MISMATCH: {'MediaTek' if target.is_mediatek else 'Exynos/Snapdragon'} vs {'MediaTek' if current.is_mediatek else 'Exynos/Snapdragon'}"
        return result
    if target.binary_version_int < current.binary_version_int:
        result["reason"] = f"ROLLBACK BLOCKED: BL v{target.binary_version} < v{current.binary_version}"
        return result
    result["allowed"] = True
    if target.binary_version_int == current.binary_version_int:
        result["reason"] = f"Same BL version ({target.binary_version}). Flash allowed."
    else:
        result["reason"] = f"BL upgrade: v{current.binary_version} → v{target.binary_version}. ONE-WAY operation."
        result["warning"] = f"Cannot downgrade below v{target.binary_version} after flashing."
    return result


def format_result(r):
    if not r.valid:
        return f"ERROR: {r.error}"
    lines = [
        f"═══════════════════════════════════════════════════",
        f"  SAMSUNG FIRMWARE STRING DECODER",
        f"═══════════════════════════════════════════════════",
        f"  Input: {r.raw}",
        f"  Hardware:     {r.hardware} — {r.series_name} {r.model_name}",
        f"  Variant:      {r.variant_name} ({r.variant_code})",
        f"  CSC:          {r.market} — {r.csc_group}",
        f"  Bootloader:   v{r.binary_version} (level {r.binary_version_int})",
        f"  Type:         {r.type_name} ({r.type_code})",
        f"  Build:        {r.month_name} {r.year} | Seq: {r.build_sequence} | Rev: {r.sub_revision}",
        f"  Chipset:      {r.chipset_hint} {'(MediaTek — Odin on Windows required)' if r.is_mediatek else ''}",
        f"  Android:      ~{r.android_version}",
        f"═══════════════════════════════════════════════════",
    ]
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Samsung Firmware String Parser")
    parser.add_argument("firmware", nargs="?", help="13-char firmware string")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check", nargs=2, metavar=("TARGET", "CURRENT"), help="Rollback check")
    args = parser.parse_args()

    if args.check:
        result = can_flash(args.check[0], args.check[1])
        status = "ALLOWED" if result["allowed"] else "BLOCKED"
        print(f"\n  Rollback Check: {status}")
        print(f"  Target BL:  v{result['target_bl']}")
        print(f"  Current BL: v{result['current_bl']}")
        print(f"  Hardware:   {'Match' if result['hardware_match'] else 'MISMATCH'}")
        print(f"  Chipset:    {'Match' if result['chipset_match'] else 'MISMATCH'}")
        print(f"\n  {result['reason']}")
        if result.get("warning"):
            print(f"\n  WARNING: {result['warning']}")
        print()
        return

    if not args.firmware:
        parser.print_help()
        sys.exit(1)

    r = parse_firmware_string(args.firmware)
    if args.json:
        print(json.dumps(asdict(r), indent=2))
    else:
        print(format_result(r))


if __name__ == "__main__":
    main()
