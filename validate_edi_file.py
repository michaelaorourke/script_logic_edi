#!/usr/bin/env python3
"""Validate EDI 837 file format for compliance."""

import sys
import re
from pathlib import Path


def validate_edi_file(file_path: str):
    """Validate EDI file format.

    Args:
        file_path: Path to EDI file
    """
    print(f"\n{'='*60}")
    print(f"EDI 837 FILE VALIDATION")
    print(f"{'='*60}")
    print(f"File: {file_path}\n")

    with open(file_path, 'r') as f:
        content = f.read()

    # Split into segments
    segments = content.split('~')
    print(f"Total segments: {len(segments)}")

    errors = []
    warnings = []

    # Check ISA segment (must be first and exactly 106 chars including ~)
    if segments[0].startswith('ISA'):
        isa_length = len(segments[0]) + 1  # Add 1 for the ~ delimiter
        if isa_length != 106:
            errors.append(f"ISA segment length is {isa_length}, must be 106")
        else:
            print("✅ ISA segment length: 106 (correct)")

        # Extract control numbers
        isa_parts = segments[0].split('*')
        if len(isa_parts) >= 14:
            interchange_num = isa_parts[13]
            print(f"   Interchange Control Number: {interchange_num}")

    # Check date formats in segments
    date_pattern = re.compile(r'\d{8}')  # YYYYMMDD format
    iso_date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}T')  # ISO format (bad)

    for i, segment in enumerate(segments[:100]):  # Check first 100 segments
        # Check for ISO dates (should not exist)
        if iso_date_pattern.search(segment):
            errors.append(f"Segment {i}: Contains ISO date format: {segment[:50]}...")

        # Check DTP segments for date format
        if segment.startswith('DTP'):
            parts = segment.split('*')
            if len(parts) >= 4:
                date_value = parts[3]
                if date_value and not date_pattern.match(date_value):
                    if 'T' in date_value or '-' in date_value:
                        errors.append(f"DTP segment {i}: Invalid date format '{date_value}' - must be YYYYMMDD")

        # Check DTM segments for date format
        if segment.startswith('DTM'):
            parts = segment.split('*')
            if len(parts) >= 3:
                date_value = parts[2]
                if date_value and not date_pattern.match(date_value):
                    if 'T' in date_value or '-' in date_value:
                        errors.append(f"DTM segment {i}: Invalid date format '{date_value}' - must be YYYYMMDD")

        # Check DMG segment (demographics with date of birth)
        if segment.startswith('DMG'):
            parts = segment.split('*')
            if len(parts) >= 3:
                date_value = parts[2]
                if date_value and not date_pattern.match(date_value):
                    if 'T' in date_value or '-' in date_value:
                        errors.append(f"DMG segment {i}: Invalid date format '{date_value}' - must be YYYYMMDD")

    # Check control number matching
    isa_control = None
    iea_control = None
    gs_control = None
    ge_control = None
    st_control = None
    se_control = None

    for segment in segments:
        if segment.startswith('ISA'):
            isa_control = segment.split('*')[13]
        elif segment.startswith('IEA'):
            iea_control = segment.split('*')[2] if len(segment.split('*')) > 2 else None
        elif segment.startswith('GS'):
            gs_control = segment.split('*')[6] if len(segment.split('*')) > 6 else None
        elif segment.startswith('GE'):
            ge_control = segment.split('*')[2] if len(segment.split('*')) > 2 else None
        elif segment.startswith('ST'):
            st_control = segment.split('*')[2] if len(segment.split('*')) > 2 else None
        elif segment.startswith('SE'):
            se_control = segment.split('*')[2] if len(segment.split('*')) > 2 else None

    # Validate control number matching
    if isa_control and iea_control:
        if isa_control == iea_control:
            print(f"✅ ISA/IEA control numbers match: {isa_control}")
        else:
            errors.append(f"ISA/IEA control number mismatch: {isa_control} != {iea_control}")

    if gs_control and ge_control:
        if gs_control == ge_control:
            print(f"✅ GS/GE control numbers match: {gs_control}")
        else:
            errors.append(f"GS/GE control number mismatch: {gs_control} != {ge_control}")

    if st_control and se_control:
        if st_control == se_control:
            print(f"✅ ST/SE control numbers match: {st_control}")
        else:
            errors.append(f"ST/SE control number mismatch: {st_control} != {se_control}")

    # Check for required segments
    required = ['ISA', 'GS', 'ST', 'BHT', 'NM1', 'SE', 'GE', 'IEA']
    found = {req: False for req in required}

    for segment in segments:
        for req in required:
            if segment.startswith(req):
                found[req] = True

    print("\nRequired segments:")
    for req, present in found.items():
        if present:
            print(f"✅ {req} - Present")
        else:
            errors.append(f"Missing required segment: {req}")
            print(f"❌ {req} - Missing")

    # Summary
    print(f"\n{'='*60}")
    if errors:
        print(f"❌ VALIDATION FAILED - {len(errors)} errors found:")
        for i, error in enumerate(errors[:10], 1):  # Show first 10 errors
            print(f"   {i}. {error}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    else:
        print("✅ VALIDATION PASSED - File format is correct")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for warning in warnings[:5]:
            print(f"   ⚠️  {warning}")

    print(f"{'='*60}\n")

    return len(errors) == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_edi_file.py <edi_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    success = validate_edi_file(file_path)
    sys.exit(0 if success else 1)