#!/usr/bin/env python3
"""Compare claims between fixed-width format and EDI 837 format files."""

import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def parse_fixed_width_file(file_path: str) -> Dict[str, List[Dict]]:
    """Parse the fixed-width format file and extract claim information.

    Returns a dictionary with claim_number as key and list of line items as value.
    """
    claims = defaultdict(list)
    current_claim = None

    with open(file_path, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue

            # Header line starts with 'H'
            if line.startswith('H'):
                # Extract claim number (found at position 236, extends to 248)
                claim_num_start = 236
                claim_num = line[claim_num_start:claim_num_start+13].strip()

                # Extract patient name
                last_name = line[92:132].strip() if len(line) > 132 else ''
                first_name = line[132:192].strip() if len(line) > 192 else ''

                # Extract dates
                billing_date = line[82:92].strip() if len(line) > 92 else ''
                dob = line[390:400].strip() if len(line) > 400 else ''
                doi = line[420:430].strip() if len(line) > 430 else ''

                current_claim = {
                    'claim_number': claim_num,
                    'patient_name': f"{last_name}, {first_name}",
                    'billing_date': billing_date,
                    'dob': dob,
                    'doi': doi,
                    'line_items': []
                }

            # Detail line starts with 'D'
            elif line.startswith('D') and current_claim:
                # Extract prescription details
                rx_num = line[1:11].strip()

                # Extract prescriber name
                prescriber_last = line[52:82].strip()
                prescriber_first = line[82:112].strip()

                # Extract quantity and days supply
                quantity = line[112:120].strip() if len(line) > 120 else ''
                days_supply = line[47:52].strip() if len(line) > 52 else ''

                # Extract amount
                amount = line[120:132].strip() if len(line) > 132 else ''

                detail = {
                    'rx_number': rx_num,
                    'prescriber': f"{prescriber_last}, {prescriber_first}",
                    'quantity': quantity,
                    'days_supply': days_supply,
                    'amount': amount
                }

                current_claim['line_items'].append(detail)

                # Store/update the claim
                if current_claim['claim_number'] not in claims:
                    claims[current_claim['claim_number']] = current_claim
                else:
                    # Update existing claim with new line item
                    claims[current_claim['claim_number']]['line_items'].append(detail)

    return claims


def parse_edi_file(file_path: str) -> Dict[str, Dict]:
    """Parse EDI 837 file and extract claim information.

    Returns a dictionary with claim_number as key and claim data as value.
    """
    claims = {}

    with open(file_path, 'r') as f:
        content = f.read()

    segments = content.split('~')

    current_claim = None
    current_patient = None

    for i, segment in enumerate(segments):
        # Patient name
        if segment.startswith('NM1*QC'):
            parts = segment.split('*')
            if len(parts) > 4:
                current_patient = f"{parts[3]}, {parts[4]}"

        # Claim number reference
        elif segment.startswith('REF*Y4'):
            parts = segment.split('*')
            if len(parts) > 1:
                claim_number = parts[2]
                current_claim = {
                    'claim_number': claim_number,
                    'patient_name': current_patient,
                    'line_items': [],
                    'total_amount': 0
                }
                claims[claim_number] = current_claim

        # Claim amount
        elif segment.startswith('CLM') and current_claim:
            parts = segment.split('*')
            if len(parts) > 2:
                try:
                    current_claim['total_amount'] = float(parts[2])
                except:
                    pass

        # Service line with NDC/prescription info
        elif segment.startswith('SV1') and current_claim:
            parts = segment.split('*')
            if len(parts) > 5:
                # Extract amount and quantity
                line_item = {
                    'amount': parts[2] if len(parts) > 2 else '',
                    'quantity': parts[5] if len(parts) > 5 else ''
                }
                current_claim['line_items'].append(line_item)

        # NDC code
        elif segment.startswith('LIN') and current_claim and current_claim['line_items']:
            parts = segment.split('*')
            if len(parts) > 3 and parts[2] == 'N4':
                current_claim['line_items'][-1]['ndc'] = parts[3]

        # Prescription number
        elif segment.startswith('REF*XZ') and current_claim and current_claim['line_items']:
            parts = segment.split('*')
            if len(parts) > 2:
                current_claim['line_items'][-1]['rx_number'] = parts[2]

    return claims


def compare_files(fixed_width_path: str, edi_path: str):
    """Compare claims between the two file formats."""

    print("=" * 80)
    print("COMPARING FILE FORMATS")
    print("=" * 80)

    # Parse both files
    print(f"\nParsing fixed-width file: {fixed_width_path}")
    fixed_claims = parse_fixed_width_file(fixed_width_path)

    print(f"Parsing EDI 837 file: {edi_path}")
    edi_claims = parse_edi_file(edi_path)

    # Get claim numbers from both files
    fixed_claim_nums = set(fixed_claims.keys())
    edi_claim_nums = set(edi_claims.keys())

    print(f"\nFixed-width file claims: {len(fixed_claim_nums)}")
    print(f"EDI 837 file claims: {len(edi_claim_nums)}")

    # Find matches and differences
    matching_claims = fixed_claim_nums & edi_claim_nums
    only_in_fixed = fixed_claim_nums - edi_claim_nums
    only_in_edi = edi_claim_nums - fixed_claim_nums

    print(f"\nMatching claim numbers: {len(matching_claims)}")
    print(f"Only in fixed-width: {len(only_in_fixed)}")
    print(f"Only in EDI 837: {len(only_in_edi)}")

    # Show sample of matching claims
    if matching_claims:
        print("\n" + "=" * 80)
        print("SAMPLE MATCHING CLAIMS (first 5):")
        print("=" * 80)

        for claim_num in sorted(matching_claims)[:5]:
            fixed_claim = fixed_claims[claim_num]
            edi_claim = edi_claims[claim_num]

            print(f"\nClaim Number: {claim_num}")
            print(f"  Fixed-width patient: {fixed_claim.get('patient_name', 'N/A')}")
            print(f"  EDI patient: {edi_claim.get('patient_name', 'N/A')}")
            print(f"  Fixed-width line items: {len(fixed_claim.get('line_items', []))}")
            print(f"  EDI line items: {len(edi_claim.get('line_items', []))}")

    # Show claims only in fixed-width
    if only_in_fixed:
        print("\n" + "=" * 80)
        print(f"CLAIMS ONLY IN FIXED-WIDTH FILE (showing up to 10):")
        print("=" * 80)

        for claim_num in sorted(only_in_fixed)[:10]:
            claim = fixed_claims[claim_num]
            print(f"  {claim_num}: {claim.get('patient_name', 'N/A')}")

    # Show claims only in EDI
    if only_in_edi:
        print("\n" + "=" * 80)
        print(f"CLAIMS ONLY IN EDI FILE (showing up to 10):")
        print("=" * 80)

        for claim_num in sorted(only_in_edi)[:10]:
            claim = edi_claims[claim_num]
            print(f"  {claim_num}: {claim.get('patient_name', 'N/A')}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total unique claims in fixed-width: {len(fixed_claim_nums)}")
    print(f"Total unique claims in EDI 837: {len(edi_claim_nums)}")
    print(f"Matching claims: {len(matching_claims)}")
    print(f"Match rate: {len(matching_claims) / max(len(fixed_claim_nums), len(edi_claim_nums)) * 100:.1f}%")

    return {
        'fixed_claims': fixed_claims,
        'edi_claims': edi_claims,
        'matching': matching_claims,
        'only_fixed': only_in_fixed,
        'only_edi': only_in_edi
    }


if __name__ == "__main__":
    # File paths
    fixed_width_file = "/Users/michaelorourke/Downloads/scriptlogic_slmia_12152025.txt"
    edi_file = "837_output/837_mongo_SLMIA_20251215_20251215_091811.txt"

    # Run comparison
    results = compare_files(fixed_width_file, edi_file)