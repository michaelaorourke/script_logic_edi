#!/usr/bin/env python3
"""Process MongoDB claim_detail collection to EDI 837 format.

This module replaces CSV-based processing with direct MongoDB queries,
filtering by billing_date and group_id.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edi_generator.config.settings import Settings, DatabaseConfig
from edi_generator.database.connection import DatabaseConnection
from edi_generator.edi.generator import EDIGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration constants
GROUP_ID = "SLMIA"  # Default group ID for Midwestern Insurance Alliance
DEFAULT_PORT = 27018  # Port forwarding port for production DB


def convert_iso_to_yyyymmdd(iso_date: Any) -> str:
    """Convert various date formats to YYYYMMDD.

    Args:
        iso_date: Date in various formats (datetime, string ISO, or YYYYMMDD)

    Returns:
        Date string in YYYYMMDD format
    """
    if not iso_date:
        return ''

    try:
        # Handle datetime objects
        if isinstance(iso_date, datetime):
            return iso_date.strftime('%Y%m%d')

        # Handle string dates
        iso_date_str = str(iso_date)

        # Handle ISO format with timezone
        if 'T' in iso_date_str:
            date_part = iso_date_str.split('T')[0]
            if date_part:
                return date_part.replace('-', '')
        # Handle YYYY-MM-DD format
        elif '-' in iso_date_str:
            return iso_date_str.replace('-', '')
        # Already in YYYYMMDD format or invalid
        return iso_date_str
    except Exception as e:
        logger.warning(f"Could not convert date {iso_date}: {e}")
        return ''


def parse_billing_date(billing_date_str: str) -> datetime:
    """Parse billing date string to datetime object.

    Args:
        billing_date_str: Date in format YYYY-MM-DD or YYYYMMDD

    Returns:
        datetime object for the billing date

    Raises:
        ValueError: If date format is invalid
    """
    # Try different date formats
    formats = ['%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']

    for fmt in formats:
        try:
            return datetime.strptime(billing_date_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {billing_date_str}. Expected YYYY-MM-DD, YYYYMMDD, or MM/DD/YYYY")


def fetch_claims_for_billing(
    db_connection: DatabaseConnection,
    billing_date: str,
    group_id: str = GROUP_ID
) -> List[Dict[str, Any]]:
    """Fetch all documents from claim_detail for the given billing_date and group_id.

    Args:
        db_connection: Active database connection
        billing_date: Billing date in string format (YYYY-MM-DD or YYYYMMDD)
        group_id: Group ID to filter by (default: SLMIA)

    Returns:
        List of claim documents from MongoDB
    """
    try:
        # Parse the billing date
        billing_dt = parse_billing_date(billing_date)

        # Create start and end of day for date range query
        start_of_day = billing_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        collection = db_connection.db["claim_detail"]

        # First, check a sample document to understand the billing_date field type
        sample = collection.find_one({"group_id": group_id})

        if sample and 'billing_date' in sample:
            billing_date_value = sample['billing_date']
            logger.info(f"Sample billing_date type: {type(billing_date_value)}, value: {billing_date_value}")

            # Build the query based on the field type
            if isinstance(billing_date_value, datetime):
                # BSON Date type - use date range
                query = {
                    "group_id": group_id,
                    "billing_date": {
                        "$gte": start_of_day,
                        "$lt": end_of_day
                    }
                }
                logger.info(f"Using date range query: {start_of_day} to {end_of_day}")
            else:
                # String type - use exact match
                # Try different string formats
                possible_formats = [
                    billing_dt.strftime('%Y-%m-%d'),
                    billing_dt.strftime('%Y%m%d'),
                    billing_dt.strftime('%-m/%-d/%Y'),  # Without leading zeros
                    billing_dt.strftime('%m/%d/%Y')     # With leading zeros
                ]

                # First try to find which format is used
                for fmt in possible_formats:
                    count = collection.count_documents({
                        "group_id": group_id,
                        "billing_date": fmt
                    })
                    if count > 0:
                        query = {
                            "group_id": group_id,
                            "billing_date": fmt
                        }
                        logger.info(f"Using string match query with format: {fmt}")
                        break
                else:
                    # Default to most likely format
                    query = {
                        "group_id": group_id,
                        "billing_date": billing_dt.strftime('%Y-%m-%d')
                    }
                    logger.warning(f"No matching format found, using default: {billing_dt.strftime('%Y-%m-%d')}")
        else:
            # No sample found or no billing_date field, try with date object
            query = {
                "group_id": group_id,
                "billing_date": {
                    "$gte": start_of_day,
                    "$lt": end_of_day
                }
            }
            logger.warning("No sample document found, defaulting to date range query")

        # Execute the query
        logger.info(f"Executing MongoDB query: {query}")
        claims = list(collection.find(query))

        logger.info(f"Retrieved {len(claims)} claims for billing_date={billing_date} and group_id={group_id}")

        # If no results, log some debugging info
        if len(claims) == 0:
            # Check if group_id exists
            group_count = collection.count_documents({"group_id": group_id})
            logger.warning(f"No claims found. Documents with group_id='{group_id}': {group_count}")

            # Check distinct billing_date values for this group (limit to 10)
            distinct_dates = collection.distinct("billing_date", {"group_id": group_id})[:10]
            logger.warning(f"Sample billing_dates for this group: {distinct_dates}")

        return claims

    except Exception as e:
        logger.error(f"Error fetching claims from MongoDB: {e}")
        raise


def transform_mongo_to_claim_format(mongo_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Transform MongoDB document to the claim format expected by EDI generator.

    Args:
        mongo_doc: Document from MongoDB claim_detail collection

    Returns:
        Transformed claim dictionary for EDI generation
    """
    # Transform MongoDB document to match expected claim format
    claim = {
        # Main claim fields
        'claim_id': str(mongo_doc.get('claim_id', '')),
        'claim_number': mongo_doc.get('claim_number', ''),
        'subscriber_num': mongo_doc.get('subscriber_num', ''),
        'status': mongo_doc.get('status', ''),

        # Patient data (embedded)
        'patient_data': {
            'first_name': mongo_doc.get('first_name', ''),
            'last_name': mongo_doc.get('last_name', ''),
            'date_of_injury': convert_iso_to_yyyymmdd(mongo_doc.get('date_of_injury', '')),
            'gender': 'M' if str(mongo_doc.get('ssno', '')).endswith(('1', '3', '5', '7', '9')) else 'F',
            'address1': str(mongo_doc.get('patient_address', '')).split(',')[0] if mongo_doc.get('patient_address') else '',
            'city': str(mongo_doc.get('patient_address', '')).split(',')[1].strip() if ',' in str(mongo_doc.get('patient_address', '')) else '',
            'state': str(mongo_doc.get('patient_address', '')).split(',')[2].strip()[:2] if str(mongo_doc.get('patient_address', '')).count(',') >= 2 else '',
            'zip': '00000',  # Default if not available
            'claim_number': mongo_doc.get('claim_number', ''),
            'dob': convert_iso_to_yyyymmdd(mongo_doc.get('dob', ''))
        },

        # Client data (embedded)
        'client_data': {
            'name': mongo_doc.get('client_name', ''),
            'client_id': str(mongo_doc.get('client_id', '')),
            'address1': str(mongo_doc.get('client_address', '')).split(',')[0] if mongo_doc.get('client_address') else '',
            'city': str(mongo_doc.get('client_address', '')).split(',')[1].strip() if ',' in str(mongo_doc.get('client_address', '')) else '',
            'state': str(mongo_doc.get('client_address', '')).split(',')[2].strip()[:2] if str(mongo_doc.get('client_address', '')).count(',') >= 2 else 'KY',
            'zip': '40253'  # Default Louisville KY zip
        },

        # Pharmacy data
        'pharmacy_npi': str(mongo_doc.get('pharmacy_npi', '')),
        'pharmacy': mongo_doc.get('pharmacy', ''),
        'pharmacy_address': mongo_doc.get('pharmacy_address', ''),

        # Prescriber data
        'doctor_no': str(mongo_doc.get('doctor_no', '')),
        'prescriber_name': mongo_doc.get('prescriber_name', ''),

        # Prescription data
        'trans_date': convert_iso_to_yyyymmdd(mongo_doc.get('trans_date', '')),
        'rx_date': convert_iso_to_yyyymmdd(mongo_doc.get('rx_date', '')),
        'rx_no': str(mongo_doc.get('rx_no', '')),
        'drug_name': mongo_doc.get('drug_name', ''),
        'ndc': str(mongo_doc.get('ndc', '')),
        'quantity': float(mongo_doc.get('quantity', 0)),
        'days_supply': int(float(mongo_doc.get('days_supply', 0))),
        'daw': str(mongo_doc.get('daw', '0')),
        'brand_gen': mongo_doc.get('brand_gen', 'G'),

        # Pricing
        'u_and_c': float(mongo_doc.get('u_and_c', 0)),
        'plan_paid': float(mongo_doc.get('plan_paid', 0)),
        'member_paid': float(mongo_doc.get('member_paid', 0)),
        'fee_schedule': float(mongo_doc.get('fee_schedule', 0)),
        'due_amount': float(mongo_doc.get('due_amount', 0)),

        # Additional fields
        '_id': mongo_doc.get('_id', {})
    }

    # Add embedded NPI data (empty for now, would need lookup)
    claim['pharmacy_npi_data'] = {}
    claim['prescriber_npi_data'] = {}

    return claim


def main():
    """Main entry point for MongoDB to EDI processor."""

    parser = argparse.ArgumentParser(
        description='Generate EDI 837 files from MongoDB claim_detail collection'
    )
    parser.add_argument(
        'billing_date',
        help='Billing date to process (format: YYYY-MM-DD or YYYYMMDD)'
    )
    parser.add_argument(
        '--group-id',
        default=GROUP_ID,
        help=f'Group ID to filter by (default: {GROUP_ID})'
    )
    parser.add_argument(
        '--mongo-uri',
        help='MongoDB URI (default: uses config or localhost:27018 for port forwarding)'
    )
    parser.add_argument(
        '--output-dir',
        default='837_output',
        help='Output directory for EDI files (default: 837_output)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of claims to process (for testing)'
    )

    args = parser.parse_args()

    # Setup MongoDB connection
    settings = Settings()

    # Override MongoDB URI if provided (for port forwarding)
    if args.mongo_uri:
        settings.database.uri = args.mongo_uri
    elif DEFAULT_PORT != 27017:
        # Use port forwarding port by default
        settings.database.uri = f"mongodb://localhost:{DEFAULT_PORT}/?directConnection=true"
        logger.info(f"Using port forwarding connection on port {DEFAULT_PORT}")

    # Create database connection
    db_conn = DatabaseConnection(settings.database)

    if not db_conn.connect():
        logger.error("Failed to connect to MongoDB")
        sys.exit(1)

    try:
        # Fetch claims from MongoDB
        logger.info(f"Fetching claims for billing_date={args.billing_date}, group_id={args.group_id}")
        mongo_claims = fetch_claims_for_billing(
            db_conn,
            args.billing_date,
            args.group_id
        )

        if not mongo_claims:
            logger.warning("No claims found for the specified criteria")
            sys.exit(0)

        # Apply limit if specified
        if args.limit:
            mongo_claims = mongo_claims[:args.limit]
            logger.info(f"Limited to {len(mongo_claims)} claims")

        # Transform MongoDB documents to claim format
        logger.info("Transforming MongoDB documents to claim format...")
        claims = [transform_mongo_to_claim_format(doc) for doc in mongo_claims]

        # Get unique claim numbers for logging
        unique_claims = len(set(c['claim_number'] for c in claims))
        logger.info(f"Processing {len(claims)} records for {unique_claims} unique claims")

        # Generate EDI
        logger.info("Generating EDI segments...")
        generator = EDIGenerator(settings)
        segments = generator.generate_from_claims(claims)

        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        billing_date_clean = args.billing_date.replace('-', '')
        output_file = f"{args.output_dir}/837_mongo_{args.group_id}_{billing_date_clean}_{timestamp}.txt"

        # Ensure output directory exists
        Path(args.output_dir).mkdir(exist_ok=True)

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
        logger.info(f"   Billing date: {args.billing_date}")
        logger.info(f"   Group ID: {args.group_id}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Error processing claims: {e}")
        return 1

    finally:
        db_conn.close()


if __name__ == "__main__":
    sys.exit(main())