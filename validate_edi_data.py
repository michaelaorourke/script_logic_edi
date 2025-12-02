#!/usr/bin/env python3
"""Validate EDI 837 data against source CSV."""

import sys
import csv
import re
from pathlib import Path
from collections import defaultdict


def extract_edi_data(file_path: str):
    """Extract key data from EDI file."""
    with open(file_path, 'r') as f:
        content = f.read()

    segments = content.split('~')

    data = {
        'claim_numbers': set(),
        'patient_names': [],
        'rx_numbers': set(),
        'ndcs': set(),
        'prescriber_npis': set(),
        'pharmacy_npis': set(),
        'header_info': {},
        'service_dates': set(),
        'total_amounts': [],
        'claim_count': 0
    }

    for segment in segments:
        # ISA segment - interchange header
        if segment.startswith('ISA'):
            parts = segment.split('*')
            data['header_info']['sender_id'] = parts[6].strip() if len(parts) > 6 else ''
            data['header_info']['receiver_id'] = parts[8].strip() if len(parts) > 8 else ''
            data['header_info']['interchange_control'] = parts[13] if len(parts) > 13 else ''

        # GS segment - functional group
        elif segment.startswith('GS'):
            parts = segment.split('*')
            data['header_info']['group_sender'] = parts[2] if len(parts) > 2 else ''
            data['header_info']['group_receiver'] = parts[3] if len(parts) > 3 else ''

        # BHT segment - transaction info
        elif segment.startswith('BHT'):
            parts = segment.split('*')
            data['header_info']['reference_id'] = parts[3] if len(parts) > 3 else ''

        # NM1*41 - Submitter
        elif segment.startswith('NM1*41'):
            parts = segment.split('*')
            data['header_info']['submitter'] = parts[3] if len(parts) > 3 else ''
            data['header_info']['submitter_id'] = parts[9] if len(parts) > 9 else ''

        # NM1*40 - Receiver
        elif segment.startswith('NM1*40'):
            parts = segment.split('*')
            data['header_info']['receiver_name'] = parts[3] if len(parts) > 3 else ''

        # NM1*85 - Billing Provider
        elif segment.startswith('NM1*85'):
            parts = segment.split('*')
            data['header_info']['billing_provider'] = parts[3] if len(parts) > 3 else ''
            data['header_info']['billing_npi'] = parts[9] if len(parts) > 9 else ''

        # NM1*PR - Payer
        elif segment.startswith('NM1*PR'):
            parts = segment.split('*')
            data['header_info']['payer_name'] = parts[3] if len(parts) > 3 else ''
            data['header_info']['payer_id'] = parts[9] if len(parts) > 9 else ''

        # REF*Y4 - Claim Number Reference
        elif segment.startswith('REF*Y4'):
            parts = segment.split('*')
            if len(parts) > 2:
                claim_num = parts[2]
                if claim_num and not claim_num.startswith('999'):
                    data['claim_numbers'].add(claim_num)

        # NM1*QC - Patient
        elif segment.startswith('NM1*QC'):
            parts = segment.split('*')
            if len(parts) > 4:
                last_name = parts[3]
                first_name = parts[4] if len(parts) > 4 else ''
                data['patient_names'].append(f"{last_name}, {first_name}")

        # CLM - Claim
        elif segment.startswith('CLM'):
            parts = segment.split('*')
            if len(parts) > 2:
                amount = parts[2]
                try:
                    data['total_amounts'].append(float(amount))
                except:
                    pass
            data['claim_count'] += 1

        # DTP*472 - Service Date
        elif segment.startswith('DTP*472'):
            parts = segment.split('*')
            if len(parts) > 3:
                data['service_dates'].add(parts[3])

        # REF*6R - Prescription Number
        elif segment.startswith('REF*6R'):
            parts = segment.split('*')
            if len(parts) > 2:
                data['rx_numbers'].add(parts[2])

        # LIN - Drug/NDC
        elif segment.startswith('LIN'):
            parts = segment.split('*')
            if len(parts) > 3:
                ndc = parts[3]
                if ndc and len(ndc) > 5:
                    data['ndcs'].add(ndc)

        # NM1*DK - Prescriber
        elif segment.startswith('NM1*DK'):
            parts = segment.split('*')
            if len(parts) > 9:
                data['prescriber_npis'].add(parts[9])

        # NM1*77 - Service Facility (Pharmacy)
        elif segment.startswith('NM1*77'):
            parts = segment.split('*')
            if len(parts) > 9:
                data['pharmacy_npis'].add(parts[9])

    return data


def load_csv_data(csv_path: str):
    """Load and summarize CSV data."""
    data = {
        'claim_numbers': set(),
        'patient_names': [],
        'rx_numbers': set(),
        'ndcs': set(),
        'prescriber_npis': set(),
        'pharmacy_npis': set(),
        'total_records': 0,
        'client_name': '',
        'service_dates': set()
    }

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data['total_records'] += 1
            data['claim_numbers'].add(row.get('claim_number', ''))

            # Patient name
            last = row.get('last_name', '')
            first = row.get('first_name', '')
            if last or first:
                data['patient_names'].append(f"{last}, {first}")

            data['rx_numbers'].add(row.get('rx_no', ''))
            data['ndcs'].add(row.get('ndc', ''))
            data['prescriber_npis'].add(row.get('doctor_no', ''))
            data['pharmacy_npis'].add(row.get('pharmacy_npi', ''))
            data['client_name'] = row.get('client_name', '')

            # Convert date format for comparison
            trans_date = row.get('trans_date', '')
            if trans_date and 'T' in trans_date:
                date_part = trans_date.split('T')[0].replace('-', '')
                data['service_dates'].add(date_part)

    return data


def validate_data(edi_path: str, csv_path: str):
    """Compare EDI data with CSV source."""
    print(f"\n{'='*60}")
    print("EDI DATA VALIDATION REPORT")
    print(f"{'='*60}\n")

    edi_data = extract_edi_data(edi_path)
    csv_data = load_csv_data(csv_path)

    # Header Constants
    print("HEADER CONSTANTS:")
    print("-" * 40)
    print(f"Sender ID:          {edi_data['header_info'].get('sender_id', 'N/A')}")
    print(f"Receiver ID:        {edi_data['header_info'].get('receiver_id', 'N/A')}")
    print(f"Submitter:          {edi_data['header_info'].get('submitter', 'N/A')}")
    print(f"Submitter ID:       {edi_data['header_info'].get('submitter_id', 'N/A')}")
    print(f"Billing Provider:   {edi_data['header_info'].get('billing_provider', 'N/A')}")
    print(f"Billing NPI:        {edi_data['header_info'].get('billing_npi', 'N/A')}")
    print(f"Payer Name:         {edi_data['header_info'].get('payer_name', 'N/A')}")
    print(f"Payer ID:           {edi_data['header_info'].get('payer_id', 'N/A')}")

    # Expected values check
    expected_checks = []
    if edi_data['header_info'].get('sender_id') == 'SCRIPTLOGIC':
        expected_checks.append("✅ Sender ID correct")
    else:
        expected_checks.append(f"❌ Sender ID: Expected 'SCRIPTLOGIC', got '{edi_data['header_info'].get('sender_id')}'")

    if edi_data['header_info'].get('receiver_id') == '205367462':
        expected_checks.append("✅ Receiver ID correct")
    else:
        expected_checks.append(f"❌ Receiver ID: Expected '205367462', got '{edi_data['header_info'].get('receiver_id')}'")

    if edi_data['header_info'].get('payer_name') == csv_data['client_name']:
        expected_checks.append(f"✅ Payer name matches CSV: {csv_data['client_name']}")
    else:
        expected_checks.append(f"❌ Payer name mismatch")

    for check in expected_checks:
        print(check)

    # Claim Counts
    print(f"\nCLAIM COUNTS:")
    print("-" * 40)
    print(f"CSV Total Records:         {csv_data['total_records']}")
    print(f"CSV Unique Claim Numbers:  {len(csv_data['claim_numbers'])}")
    print(f"EDI CLM Segments:          {edi_data['claim_count']}")
    print(f"EDI Unique Claim Numbers:  {len(edi_data['claim_numbers'])}")

    if len(csv_data['claim_numbers']) == len(edi_data['claim_numbers']):
        print("✅ Claim number count matches")
    else:
        print(f"❌ Claim number mismatch: CSV has {len(csv_data['claim_numbers'])}, EDI has {len(edi_data['claim_numbers'])}")

    # Claim Number Comparison
    print(f"\nCLAIM NUMBER VALIDATION:")
    print("-" * 40)

    csv_claims = csv_data['claim_numbers'] - {''}
    edi_claims = edi_data['claim_numbers'] - {''}

    missing_in_edi = csv_claims - edi_claims
    extra_in_edi = edi_claims - csv_claims

    if not missing_in_edi and not extra_in_edi:
        print(f"✅ All {len(csv_claims)} claim numbers match perfectly")
    else:
        if missing_in_edi:
            print(f"❌ Missing in EDI ({len(missing_in_edi)}):")
            for claim in sorted(missing_in_edi)[:5]:
                print(f"   - {claim}")
        if extra_in_edi:
            print(f"❌ Extra in EDI ({len(extra_in_edi)}):")
            for claim in sorted(extra_in_edi)[:5]:
                print(f"   - {claim}")

    # Sample claim numbers
    print(f"\nSample Claim Numbers in EDI:")
    for claim in sorted(edi_data['claim_numbers'])[:5]:
        print(f"   {claim}")

    # Data Elements
    print(f"\nDATA ELEMENTS:")
    print("-" * 40)
    print(f"Prescription Numbers: {len(edi_data['rx_numbers'])}")
    print(f"NDCs:                {len(edi_data['ndcs'])}")
    print(f"Prescriber NPIs:     {len(edi_data['prescriber_npis'])}")
    print(f"Pharmacy NPIs:       {len(edi_data['pharmacy_npis'])}")
    print(f"Service Dates:       {len(edi_data['service_dates'])}")

    # Financial Summary
    if edi_data['total_amounts']:
        total = sum(edi_data['total_amounts'])
        print(f"\nFINANCIAL SUMMARY:")
        print("-" * 40)
        print(f"Total CLM Amount:     ${total:,.2f}")
        print(f"Average per Claim:    ${total/len(edi_data['total_amounts']):,.2f}")

    # Overall Status
    print(f"\n{'='*60}")
    errors = []
    if edi_data['header_info'].get('sender_id') != 'SCRIPTLOGIC':
        errors.append("Incorrect Sender ID")
    if len(csv_claims) != len(edi_claims):
        errors.append("Claim count mismatch")
    if missing_in_edi:
        errors.append(f"{len(missing_in_edi)} claims missing")

    if errors:
        print(f"❌ VALIDATION FAILED: {', '.join(errors)}")
    else:
        print("✅ DATA VALIDATION PASSED")
    print(f"{'='*60}\n")

    return len(errors) == 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python validate_edi_data.py <edi_file> <csv_file>")
        sys.exit(1)

    edi_file = sys.argv[1]
    csv_file = sys.argv[2]

    if not Path(edi_file).exists():
        print(f"EDI file not found: {edi_file}")
        sys.exit(1)

    if not Path(csv_file).exists():
        print(f"CSV file not found: {csv_file}")
        sys.exit(1)

    success = validate_data(edi_file, csv_file)
    sys.exit(0 if success else 1)