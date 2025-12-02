#!/usr/bin/env python3
"""Validate EDI file data matches PDF invoice data."""

import re
import sys
from pathlib import Path


def extract_pdf_data_from_edi(edi_path: str, claim_number: str):
    """Extract data for a specific claim from EDI file."""

    with open(edi_path, 'r') as f:
        content = f.read()

    segments = content.split('~')

    data = {
        'claim_number': claim_number,
        'found': False,
        'patient_name': '',
        'ndc': '',
        'rx_number': '',
        'quantity': '',
        'days_supply': '',
        'pharmacy_npi': '',
        'prescriber_npi': '',
        'amount': '',
        'date_filled': ''
    }

    # Find the claim
    claim_found = False
    claim_start_idx = -1

    for i, segment in enumerate(segments):
        # Look for claim number reference
        if segment.startswith('REF*Y4') and claim_number in segment:
            claim_found = True
            claim_start_idx = i
            data['found'] = True

            # Look backwards for patient name (before the REF*Y4 segment)
            for j in range(i-1, max(0, i-10), -1):
                if segments[j].startswith('NM1*QC'):
                    parts = segments[j].split('*')
                    if len(parts) > 4:
                        data['patient_name'] = f"{parts[3]}, {parts[4]}"
                    break

            # Also check for the CLM segment which has the amount
            for j in range(i-5, min(len(segments), i+5)):
                if segments[j].startswith('CLM') and claim_number in segments[j]:
                    parts = segments[j].split('*')
                    if len(parts) > 2:
                        data['amount'] = parts[2]
                    break

            # Look forward for prescription details - scan next 100 segments
            # to ensure we capture all service lines
            for j in range(i+1, min(len(segments), i+100)):
                seg = segments[j]

                # Service date (filled date)
                if seg.startswith('DTP*472'):
                    parts = seg.split('*')
                    if len(parts) >= 4:
                        if not data['date_filled']:  # Only capture first occurrence
                            data['date_filled'] = parts[3]

                # Prescription number
                if seg.startswith('REF*6R'):
                    parts = seg.split('*')
                    if len(parts) >= 3:
                        if not data['rx_number']:  # Only capture first occurrence
                            data['rx_number'] = parts[2]

                # NDC
                if seg.startswith('LIN') and '*N4*' in seg:
                    parts = seg.split('*')
                    if len(parts) >= 4:
                        if not data['ndc']:  # Only capture first occurrence
                            data['ndc'] = parts[3]

                # Quantity and Unit (from SV1 segment)
                if seg.startswith('SV1'):
                    parts = seg.split('*')
                    if len(parts) >= 5:
                        if not data['quantity']:  # Only capture first occurrence
                            # Extract the numeric part from quantity field
                            qty_str = parts[4]
                            # Remove any decimal points and trailing zeros
                            if '.' in qty_str:
                                qty_float = float(qty_str)
                                data['quantity'] = str(int(qty_float))
                            else:
                                data['quantity'] = qty_str
                        if not data['amount'] and len(parts) >= 3:
                            data['amount'] = parts[2]

                # Days supply (from CTP segment)
                if seg.startswith('CTP'):
                    parts = seg.split('*')
                    if len(parts) >= 5:
                        if not data['days_supply']:  # Only capture first occurrence
                            # The days supply is in position 5 (index 4)
                            days_str = parts[4]
                            # Remove any decimal points
                            if '.' in days_str:
                                days_float = float(days_str)
                                data['days_supply'] = str(int(days_float))
                            else:
                                data['days_supply'] = days_str

                # Pharmacy NPI
                if seg.startswith('NM1*77'):
                    parts = seg.split('*')
                    if len(parts) >= 10:
                        if not data['pharmacy_npi']:  # Only capture first occurrence
                            data['pharmacy_npi'] = parts[9]

                # Prescriber NPI
                if seg.startswith('NM1*DK'):
                    parts = seg.split('*')
                    if len(parts) >= 10:
                        if not data['prescriber_npi']:  # Only capture first occurrence
                            data['prescriber_npi'] = parts[9]

                # Stop if we hit another claim's REF*Y4
                if j > i+10 and seg.startswith('REF*Y4'):
                    break
                # Or if we hit another claim
                if j > i+10 and seg.startswith('CLM') and claim_number not in seg:
                    break

    return data


def validate_pdf_against_edi(edi_path: str):
    """Validate PDF data against EDI file."""

    print("\n" + "="*70)
    print("PDF TO EDI DATA VALIDATION")
    print("="*70)

    # PDF data extracted from the images
    pdf_samples = [
        {
            'claim_number': 'BH20210730001',
            'invoice': '12124',
            'patient_name': 'Roy Wayson',
            'date_filled': '11-28-2025',
            'ndc': '00406851501',
            'rx_number': '000002048434',
            'quantity': '120',
            'days_supply': '30',
            'pharmacy_npi': '1649391194',
            'prescriber_npi': '1053329268',
            'prescriber_name': 'Smith Don',
            'amount': '233.91'
        },
        {
            'claim_number': 'MP20220414005',
            'invoice': '12075',
            'patient_name': 'Shawn Sweeney',
            'date_filled': '11-14-2025',
            'ndc': '65162003310',
            'rx_number': '000004422134',
            'quantity': '60',
            'days_supply': '30',
            'pharmacy_npi': '1700969243',
            'prescriber_npi': '1497989180',
            'prescriber_name': 'Shinkle Aaron',
            'amount': '72.61'
        }
    ]

    # Check each PDF sample against EDI
    all_match = True

    for pdf in pdf_samples:
        print(f"\nClaim: {pdf['claim_number']} (Invoice #{pdf['invoice']})")
        print("-" * 50)

        edi_data = extract_pdf_data_from_edi(edi_path, pdf['claim_number'])

        if not edi_data['found']:
            print(f"❌ Claim {pdf['claim_number']} NOT FOUND in EDI")
            all_match = False
            continue

        # Compare fields
        checks = []

        # Patient name (last name match is sufficient due to formatting differences)
        pdf_last = pdf['patient_name'].split()[1] if ' ' in pdf['patient_name'] else pdf['patient_name']
        if pdf_last.upper() in edi_data['patient_name'].upper():
            checks.append(f"✅ Patient: {edi_data['patient_name']}")
        else:
            checks.append(f"❌ Patient: PDF={pdf['patient_name']}, EDI={edi_data['patient_name']}")
            all_match = False

        # Date filled (convert format)
        pdf_date_parts = pdf['date_filled'].split('-')
        if len(pdf_date_parts) == 3:
            pdf_date = f"2025{pdf_date_parts[0]}{pdf_date_parts[1]}"
            if pdf_date == edi_data['date_filled']:
                checks.append(f"✅ Date Filled: {edi_data['date_filled']}")
            else:
                checks.append(f"❌ Date: PDF={pdf_date}, EDI={edi_data['date_filled']}")

        # NDC
        if pdf['ndc'] == edi_data['ndc']:
            checks.append(f"✅ NDC: {edi_data['ndc']}")
        else:
            checks.append(f"❌ NDC: PDF={pdf['ndc']}, EDI={edi_data['ndc']}")
            all_match = False

        # Rx Number
        if pdf['rx_number'] == edi_data['rx_number']:
            checks.append(f"✅ Rx#: {edi_data['rx_number']}")
        else:
            checks.append(f"❌ Rx#: PDF={pdf['rx_number']}, EDI={edi_data['rx_number']}")
            all_match = False

        # Quantity
        if pdf['quantity'] == edi_data['quantity']:
            checks.append(f"✅ Quantity: {edi_data['quantity']}")
        else:
            checks.append(f"❌ Quantity: PDF={pdf['quantity']}, EDI={edi_data['quantity']}")
            all_match = False

        # Days Supply
        if pdf['days_supply'] == edi_data['days_supply']:
            checks.append(f"✅ Days Supply: {edi_data['days_supply']}")
        else:
            checks.append(f"❌ Days: PDF={pdf['days_supply']}, EDI={edi_data['days_supply']}")
            all_match = False

        # Pharmacy NPI
        if pdf['pharmacy_npi'] == edi_data['pharmacy_npi']:
            checks.append(f"✅ Pharmacy NPI: {edi_data['pharmacy_npi']}")
        else:
            checks.append(f"❌ Pharmacy: PDF={pdf['pharmacy_npi']}, EDI={edi_data['pharmacy_npi']}")
            all_match = False

        # Prescriber NPI
        if pdf['prescriber_npi'] == edi_data['prescriber_npi']:
            checks.append(f"✅ Prescriber NPI: {edi_data['prescriber_npi']}")
        else:
            checks.append(f"❌ Prescriber: PDF={pdf['prescriber_npi']}, EDI={edi_data['prescriber_npi']}")
            all_match = False

        for check in checks:
            print(f"   {check}")

    # Check all PDF claim numbers are in EDI
    print("\n" + "="*70)
    print("ALL PDF CLAIM NUMBERS CHECK:")
    print("-" * 50)

    # List of all claim numbers from PDF directory
    all_pdf_claims = [
        'BH20210730001', 'BH20231229004', 'BH20250305002',
        'MP20170307001', 'MP20181210001', 'MP20220221004',
        'MP20220414005', 'MP20220509001', 'MP20230124102',
        'MP20230210005', 'MP20231004003', 'MP20231211003',
        'MP20240319001', 'MP20240416004', 'MP20240516004',
        'MP20240517102', 'MP20240520002', 'MP20240722102',
        'MP20240924005', 'MP20250205102', 'MP20250304107',
        'MP20250313001', 'MP20250402003', 'MP20250724001',
        'MP20250728002', 'MP20251113005', 'MW20000309012',
        'MW20010427001', 'MW20010612002', 'MW20020809004',
        'MW20021009001', 'MW20030919001', 'MW20040526004',
        'MW20040817015', 'MW20051021007', 'MWBK24070001',
        'MWPR21120009', 'MWPR22040021', 'MX20061212001',
        'MX20100325003', 'MX20110413005', 'MX20111005005',
        'WF20221109004', 'WF20240826002', 'WF20241219102',
        'WF20250402102'
    ]

    # Check each claim exists in EDI
    with open(edi_path, 'r') as f:
        edi_content = f.read()

    missing_claims = []
    found_claims = []

    for claim in all_pdf_claims:
        if f"REF*Y4*{claim}" in edi_content:
            found_claims.append(claim)
        else:
            missing_claims.append(claim)

    print(f"Total PDF claims: {len(all_pdf_claims)}")
    print(f"Found in EDI: {len(found_claims)}")
    print(f"Missing in EDI: {len(missing_claims)}")

    if missing_claims:
        print("\n❌ Missing claims:")
        for claim in missing_claims[:10]:
            print(f"   - {claim}")
    else:
        print("\n✅ All 46 PDF claim numbers found in EDI file")

    # Final verdict
    print("\n" + "="*70)
    if all_match and not missing_claims:
        print("✅ PDF DATA VALIDATION PASSED")
        print("   All claim numbers present")
        print("   Sample data matches correctly")
    else:
        print("❌ PDF DATA VALIDATION FAILED")
        if missing_claims:
            print(f"   {len(missing_claims)} claims missing from EDI")
        if not all_match:
            print("   Data mismatches found in sample checks")
    print("="*70 + "\n")

    return all_match and not missing_claims


if __name__ == "__main__":
    if len(sys.argv) < 2:
        edi_file = "837_output/837_csv_20251202_084619.txt"
    else:
        edi_file = sys.argv[1]

    if not Path(edi_file).exists():
        print(f"EDI file not found: {edi_file}")
        sys.exit(1)

    success = validate_pdf_against_edi(edi_file)
    sys.exit(0 if success else 1)