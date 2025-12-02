#!/usr/bin/env python3
"""EDI 837 Professional Claims Generator - Main Entry Point

This script generates X12 EDI 837 files for pharmacy prescription claims
by pulling data from MongoDB and formatting according to HIPAA standards.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edi_generator.config.settings import Settings
from edi_generator.database.connection import DatabaseConnection
from edi_generator.edi.generator import EDIGenerator
from edi_generator.utils.counter_manager import EDICounterManager
from test_claim_ids import TEST_CLAIM_IDS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_date_range(date_range_str: str) -> Tuple[str, str]:
    """Parse date range string into start and end dates.

    Args:
        date_range_str: Date range in format "YYYY-MM-DD:YYYY-MM-DD"

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        ValueError: If date format is invalid
    """
    try:
        parts = date_range_str.split(':')
        if len(parts) != 2:
            raise ValueError("Date range must be in format YYYY-MM-DD:YYYY-MM-DD")

        start_date = datetime.strptime(parts[0], "%Y-%m-%d").strftime("%Y%m%d")
        end_date = datetime.strptime(parts[1], "%Y-%m-%d").strftime("%Y%m%d")

        return start_date, end_date
    except Exception as e:
        raise ValueError(f"Invalid date range format: {e}")


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Generate X12 EDI 837 Professional claims files for pharmacy prescriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query-mode all --limit 100
  %(prog)s --query-mode claim-ids --ids "id1,id2,id3"
  %(prog)s --query-mode client-id --client-id 12345
  %(prog)s --query-mode date-range --date-range "2024-01-01:2024-01-31"
  %(prog)s --query-mode status --statuses "B,NB"
  %(prog)s --test-mode  # Uses built-in test claim IDs
        """
    )

    # Query mode selection
    parser.add_argument(
        "--query-mode",
        choices=["all", "claim-ids", "client-id", "date-range", "status", "test"],
        default="all",
        help="Query mode for selecting claims"
    )

    # Query parameters
    parser.add_argument(
        "--ids",
        type=str,
        help="Comma-separated list of claim IDs (for claim-ids mode)"
    )

    parser.add_argument(
        "--client-id",
        type=str,
        help="Client ID to filter claims (for client-id mode)"
    )

    parser.add_argument(
        "--date-range",
        type=str,
        help="Date range in YYYY-MM-DD:YYYY-MM-DD format (for date-range mode)"
    )

    parser.add_argument(
        "--statuses",
        type=str,
        help="Comma-separated list of claim statuses (for status mode)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of claims to process"
    )

    # Test mode
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Use built-in test claim IDs for validation"
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: auto-generated with timestamp)"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="837_output",
        help="Output directory (default: 837_output)"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON configuration file"
    )

    parser.add_argument(
        "--save-config",
        type=str,
        help="Save current configuration to specified file"
    )

    # Database options
    parser.add_argument(
        "--mongodb-uri",
        type=str,
        help="MongoDB connection URI"
    )

    parser.add_argument(
        "--database",
        type=str,
        help="MongoDB database name"
    )

    # Debug options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data without generating output file"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate EDI output, don't write file"
    )

    # Counter management options
    parser.add_argument(
        "--show-counters",
        action="store_true",
        help="Display current EDI control number counter values"
    )

    parser.add_argument(
        "--reset-counters",
        action="store_true",
        help="Reset interchange control number counter to 1 (requires confirmation)"
    )

    parser.add_argument(
        "--set-interchange",
        type=int,
        help="Set interchange control number to specific value"
    )

    return parser


def get_test_claim_ids() -> List[str]:
    """Return list of test claim IDs for validation.

    Returns:
        List of 149 test claim IDs matching reference file
    """
    return TEST_CLAIM_IDS


def main() -> int:
    """Main entry point for the EDI generator.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle counter management operations first (no database needed)
    if args.show_counters:
        counter_mgr = EDICounterManager()
        counters = counter_mgr.get_current_values()
        print("\n" + "=" * 50)
        print("EDI Control Numbers:")
        print("=" * 50)
        print(f"  Interchange Control Number: {counters['interchange_control_number']:09d}")
        print(f"  Group Control Number:        4 (static)")
        print(f"  Transaction Control Number:  0001 (static)")
        print(f"  Last Updated:                {counters.get('last_updated', 'N/A')}")
        if 'reset_at' in counters:
            print(f"  Last Reset:                  {counters['reset_at']}")
        print("=" * 50)
        return 0

    if args.reset_counters:
        response = input("\n⚠️  Are you sure you want to reset the interchange counter to 1? (yes/no): ")
        if response.lower() == 'yes':
            counter_mgr = EDICounterManager()
            counter_mgr.reset_counters(confirm=True)
            print("✅ Interchange counter has been reset successfully")
        else:
            print("❌ Counter reset cancelled")
        return 0

    if args.set_interchange:
        counter_mgr = EDICounterManager()
        counter_mgr.set_interchange_counter(args.set_interchange)
        print(f"✅ Interchange control number set to {args.set_interchange}")
        return 0

    # Load configuration
    config_file = args.config if args.config else None
    settings = Settings(config_file=config_file)

    # Override settings from command line
    if args.mongodb_uri:
        settings.database.uri = args.mongodb_uri
    if args.database:
        settings.database.database_name = args.database
    if args.output_dir:
        settings.output.output_dir = args.output_dir

    # Save configuration if requested
    if args.save_config:
        settings.save_to_file(args.save_config)
        logger.info(f"Configuration saved to {args.save_config}")

    # Initialize database connection
    db = DatabaseConnection(settings.database)
    if not db.connect():
        logger.error("Failed to connect to database")
        return 1

    # Validate collections exist
    if not db.validate_collections():
        logger.error("Required database collections not found")
        return 1

    try:
        # Determine query parameters based on mode
        claim_ids = None
        client_id = None
        date_range = None
        statuses = None
        limit = args.limit

        if args.test_mode or args.query_mode == "test":
            # Use test claim IDs
            claim_ids = get_test_claim_ids()
            logger.info(f"Using {len(claim_ids)} test claim IDs")

        elif args.query_mode == "claim-ids":
            if not args.ids:
                logger.error("--ids parameter required for claim-ids mode")
                return 1
            claim_ids = [id.strip() for id in args.ids.split(",")]

        elif args.query_mode == "client-id":
            if not args.client_id:
                logger.error("--client-id parameter required for client-id mode")
                return 1
            client_id = args.client_id

        elif args.query_mode == "date-range":
            if not args.date_range:
                logger.error("--date-range parameter required for date-range mode")
                return 1
            date_range = parse_date_range(args.date_range)

        elif args.query_mode == "status":
            if not args.statuses:
                logger.error("--statuses parameter required for status mode")
                return 1
            statuses = [s.strip() for s in args.statuses.split(",")]

        # Query claims with optimized aggregation
        logger.info("=" * 60)
        logger.info("Querying claims from database...")
        logger.info("=" * 60)

        claims = db.get_claims_optimized(
            claim_ids=claim_ids,
            client_id=client_id,
            date_range=date_range,
            statuses=statuses,
            limit=limit
        )

        if not claims:
            logger.warning("No claims found matching criteria")
            return 0

        logger.info(f"Found {len(claims)} claims to process")

        # Generate EDI
        if not args.dry_run:
            logger.info("=" * 60)
            logger.info("Generating EDI output...")
            logger.info("=" * 60)

            generator = EDIGenerator(settings)
            segments = generator.generate_from_claims(claims)

            if args.validate_only:
                # Just validate, don't write
                errors = generator.validate_output(segments)
                if errors:
                    logger.error(f"Validation failed with {len(errors)} errors:")
                    for error in errors[:10]:  # Show first 10 errors
                        logger.error(f"  - {error}")
                    return 1
                else:
                    logger.info("✅ EDI validation passed")
                    logger.info(f"   Segments: {len(segments)}")
                    return 0

            # Write output file
            output_path = args.output
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"{settings.output.output_dir}/837_db_{timestamp}.txt"

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Write EDI file (single line, no newlines)
            with open(output_path, 'w') as f:
                f.write(''.join(segments))

            # Report statistics
            file_size = Path(output_path).stat().st_size
            logger.info("=" * 60)
            logger.info(f"✅ EDI file generated: {output_path}")
            logger.info(f"   File size: {file_size:,} bytes")
            logger.info(f"   Segments: {len(segments)}")
            logger.info(f"   Claims processed: {len(claims)}")
            logger.info("=" * 60)

        else:
            logger.info("Dry run mode - no output generated")
            logger.info(f"Would process {len(claims)} claims")

        return 0

    except Exception as e:
        logger.error(f"Error generating EDI: {e}", exc_info=args.debug)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())