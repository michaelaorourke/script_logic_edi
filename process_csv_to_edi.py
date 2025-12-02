#!/usr/bin/env python3
"""Process CSV file directly to EDI 837 format."""

import csv
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edi_generator.config.settings import Settings
from edi_generator.edi.generator import EDIGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_iso_to_yyyymmdd(iso_date: str) -> str:
    """Convert ISO date format to YYYYMMDD.

    Args:
        iso_date: Date string like '2022-04-14T00:00:00.000Z'

    Returns:
        Date string in YYYYMMDD format, e.g., '20220414'
    """
    if not iso_date:
        return ''

    try:
        # Handle ISO format with timezone
        if 'T' in iso_date:
            date_part = iso_date.split('T')[0]  # Get just the date part
            if date_part:
                # Remove any dashes
                return date_part.replace('-', '')
        # Handle YYYY-MM-DD format
        elif '-' in iso_date:
            return iso_date.replace('-', '')
        # Already in correct format or invalid
        return iso_date
    except Exception as e:
        logger.warning(f"Could not convert date {iso_date}: {e}")
        return ''


def parse_csv_to_claims(csv_file: str) -> List[Dict[str, Any]]:
    """Parse CSV file into claim format expected by EDI generator.

    Args:
        csv_file: Path to CSV file

    Returns:
        List of claim dictionaries
    """
    claims = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Transform CSV row to claim format expected by generator
            claim = {
                # Main claim fields
                'claim_id': row.get('claim_id', ''),
                'claim_number': row.get('claim_number', ''),
                'subscriber_num': row.get('subscriber_num', ''),
                'status': row.get('status', ''),

                # Patient data (embedded)
                'patient_data': {
                    'first_name': row.get('first_name', ''),
                    'last_name': row.get('last_name', ''),
                    'date_of_injury': convert_iso_to_yyyymmdd(row.get('date_of_injury', '')),
                    'gender': 'M' if row.get('ssno', '').endswith(('1', '3', '5', '7', '9')) else 'F',  # Guess from SSN
                    'address1': row.get('patient_address', '').split(',')[0] if row.get('patient_address') else '',
                    'city': row.get('patient_address', '').split(',')[1].strip() if ',' in row.get('patient_address', '') else '',
                    'state': row.get('patient_address', '').split(',')[2].strip()[:2] if row.get('patient_address', '').count(',') >= 2 else '',
                    'zip': '00000',  # Default if not available
                    'claim_number': row.get('claim_number', ''),
                    'dob': convert_iso_to_yyyymmdd(row.get('dob', ''))
                },

                # Client data (embedded)
                'client_data': {
                    'name': row.get('client_name', ''),
                    'client_id': row.get('client_id', ''),
                    'address1': row.get('client_address', '').split(',')[0] if row.get('client_address') else '',
                    'city': row.get('client_address', '').split(',')[1].strip() if ',' in row.get('client_address', '') else '',
                    'state': row.get('client_address', '').split(',')[2].strip()[:2] if row.get('client_address', '').count(',') >= 2 else 'KY',
                    'zip': '40253'  # Default Louisville KY zip from data
                },

                # Pharmacy data
                'pharmacy_npi': row.get('pharmacy_npi', ''),
                'pharmacy': row.get('pharmacy', ''),
                'pharmacy_address': row.get('pharmacy_address', ''),

                # Prescriber data
                'doctor_no': row.get('doctor_no', ''),
                'prescriber_name': row.get('prescriber_name', ''),

                # Prescription data
                'trans_date': convert_iso_to_yyyymmdd(row.get('trans_date', '')),
                'rx_date': convert_iso_to_yyyymmdd(row.get('rx_date', '')),
                'rx_no': row.get('rx_no', ''),
                'drug_name': row.get('drug_name', ''),
                'ndc': row.get('ndc', ''),
                'quantity': float(row.get('quantity', 0)),
                'days_supply': int(float(row.get('days_supply', 0))),
                'daw': row.get('daw', '0'),
                'brand_gen': row.get('brand_gen', 'G'),

                # Pricing
                'u_and_c': float(row.get('u_and_c', 0)),
                'plan_paid': float(row.get('plan_paid', 0)),
                'member_paid': float(row.get('member_paid', 0)),
                'fee_schedule': float(row.get('fee_schedule', 0)),
                'due_amount': float(row.get('due_amount', 0)),

                # Additional fields
                '_id': {'$oid': row.get('_id', '')}
            }

            # Add embedded NPI data (empty for now, would need lookup)
            claim['pharmacy_npi_data'] = {}
            claim['prescriber_npi_data'] = {}

            claims.append(claim)

    logger.info(f"Parsed {len(claims)} claims from CSV")
    return claims


def main():
    """Main entry point for CSV to EDI processor."""

    if len(sys.argv) < 2:
        print("Usage: python process_csv_to_edi.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    if not Path(csv_file).exists():
        logger.error(f"CSV file not found: {csv_file}")
        sys.exit(1)

    # Parse CSV
    logger.info(f"Processing CSV file: {csv_file}")
    claims = parse_csv_to_claims(csv_file)

    if not claims:
        logger.error("No claims found in CSV")
        sys.exit(1)

    # Get unique claim numbers for logging
    unique_claims = len(set(c['claim_number'] for c in claims))
    logger.info(f"Found {len(claims)} records for {unique_claims} unique claims")

    # Create settings
    settings = Settings()

    # Generate EDI
    logger.info("Generating EDI segments...")
    generator = EDIGenerator(settings)
    segments = generator.generate_from_claims(claims)

    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"837_output/837_csv_{timestamp}.txt"

    # Ensure output directory exists
    Path("837_output").mkdir(exist_ok=True)

    # Write EDI file
    with open(output_file, 'w') as f:
        f.write(''.join(segments))

    # Report results
    file_size = Path(output_file).stat().st_size
    logger.info("=" * 60)
    logger.info(f"✅ EDI file generated: {output_file}")
    logger.info(f"   File size: {file_size:,} bytes")
    logger.info(f"   Segments: {len(segments)}")
    logger.info(f"   Claims processed: {len(claims)}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())