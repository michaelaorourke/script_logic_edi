#!/usr/bin/env python3
"""Create MongoDB indexes for the EDI generator collections."""

import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure, ConnectionFailure
from typing import List, Tuple, Dict, Any
import argparse
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndexCreator:
    """Manages MongoDB index creation for EDI generator collections."""

    def __init__(self, uri: str = "mongodb://localhost:27018/?directConnection=true",
                 database: str = "scriptlogic"):
        """Initialize index creator.

        Args:
            uri: MongoDB connection URI
            database: Database name
        """
        self.uri = uri
        self.database_name = database
        self.client = None
        self.db = None

    def connect(self):
        """Establish database connection."""
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.database_name]
            # Test connection
            self.client.server_info()
            logger.info(f"Connected to MongoDB at {self.uri}")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def create_indexes(self) -> Dict[str, List[str]]:
        """Create all required indexes.

        Returns:
            Dictionary of collection names and created indexes
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        results = {}

        # Define indexes for each collection
        indexes = {
            "claim_detail": [
                # Compound index for main query pattern
                ([("group_id", ASCENDING), ("billing_date", DESCENDING)],
                 {"name": "idx_group_billing"}),
                # Unique constraint on claim number
                ([("claim_number", ASCENDING)],
                 {"unique": True, "name": "idx_claim_number_unique"}),
                # Index for date range queries
                ([("billing_date", DESCENDING)],
                 {"name": "idx_billing_date"}),
                # Index for group_id queries
                ([("group_id", ASCENDING)],
                 {"name": "idx_group_id"}),
            ],
            "patient": [
                # Support lookups from claim_detail
                ([("claim_number", ASCENDING)],
                 {"name": "idx_patient_claim_number"}),
            ],
            "client": [
                # Support client lookups
                ([("client_id", ASCENDING)],
                 {"unique": True, "name": "idx_client_id"}),
            ],
            "npi": [
                # Support NPI lookups
                ([("npi", ASCENDING)],
                 {"unique": True, "name": "idx_npi"}),
            ]
        }

        # Create indexes for each collection
        for collection_name, collection_indexes in indexes.items():
            collection = self.db[collection_name]
            created = []

            for index_spec, index_options in collection_indexes:
                try:
                    index_name = index_options.get("name", str(index_spec))

                    # Check if index already exists
                    existing_indexes = collection.list_indexes()
                    index_exists = any(
                        idx['name'] == index_name for idx in existing_indexes
                    )

                    if index_exists:
                        logger.info(f"Index {index_name} already exists on {collection_name}")
                        created.append(f"{index_name} (existing)")
                    else:
                        result = collection.create_index(index_spec, **index_options)
                        logger.info(f"Created index {result} on {collection_name}")
                        created.append(result)

                except OperationFailure as e:
                    logger.error(f"Failed to create index on {collection_name}: {e}")
                    # Continue with other indexes

            results[collection_name] = created

        return results

    def verify_indexes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Verify all indexes are present.

        Returns:
            Dictionary of collection names and their indexes
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        results = {}

        for collection_name in ["claim_detail", "patient", "client", "npi"]:
            collection = self.db[collection_name]
            indexes = list(collection.list_indexes())
            results[collection_name] = indexes

            logger.info(f"Collection {collection_name} has {len(indexes)} indexes:")
            for idx in indexes:
                logger.info(f"  - {idx['name']}: {idx.get('key', {})}")

        return results

    def analyze_query_performance(self, group_id: str = "SLMIA",
                                  billing_date: str = "2025-12-01") -> Dict[str, Any]:
        """Analyze query performance with explain plan.

        Args:
            group_id: Group ID to test
            billing_date: Billing date to test (YYYY-MM-DD format)

        Returns:
            Explain plan results
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        from datetime import datetime

        # Parse billing date
        date_obj = datetime.strptime(billing_date, "%Y-%m-%d")

        # Build test query
        query = {
            "group_id": group_id,
            "billing_date": {
                "$gte": date_obj.replace(hour=0, minute=0, second=0, microsecond=0),
                "$lt": date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
            }
        }

        # Run explain
        collection = self.db.claim_detail
        explain_result = collection.find(query).explain()

        # Extract key metrics
        execution_stats = explain_result.get("executionStats", {})

        performance = {
            "totalDocsExamined": execution_stats.get("totalDocsExamined", 0),
            "totalDocsReturned": execution_stats.get("nReturned", 0),
            "executionTimeMillis": execution_stats.get("executionTimeMillis", 0),
            "indexesUsed": [],
            "stage": execution_stats.get("executionStages", {}).get("stage", ""),
        }

        # Extract index usage
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
        if "inputStage" in winning_plan:
            input_stage = winning_plan["inputStage"]
            if input_stage.get("stage") == "IXSCAN":
                performance["indexesUsed"].append(input_stage.get("indexName", ""))

        logger.info(f"Query performance analysis:")
        logger.info(f"  - Docs examined: {performance['totalDocsExamined']}")
        logger.info(f"  - Docs returned: {performance['totalDocsReturned']}")
        logger.info(f"  - Execution time: {performance['executionTimeMillis']}ms")
        logger.info(f"  - Index used: {performance['indexesUsed']}")
        logger.info(f"  - Stage: {performance['stage']}")

        return performance

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")


def main():
    """Main function to create indexes."""
    parser = argparse.ArgumentParser(description="Create MongoDB indexes for EDI generator")
    parser.add_argument(
        "--uri",
        default="mongodb://localhost:27018/?directConnection=true",
        help="MongoDB connection URI"
    )
    parser.add_argument(
        "--database",
        default="scriptlogic",
        help="Database name"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing indexes, don't create new ones"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze query performance after creating indexes"
    )

    args = parser.parse_args()

    creator = IndexCreator(uri=args.uri, database=args.database)

    try:
        # Connect to database
        creator.connect()

        if args.verify_only:
            # Only verify indexes
            logger.info("Verifying existing indexes...")
            indexes = creator.verify_indexes()
        else:
            # Create indexes
            logger.info("Creating indexes...")
            created = creator.create_indexes()
            logger.info(f"Index creation complete: {created}")

            # Verify indexes
            logger.info("\nVerifying indexes...")
            indexes = creator.verify_indexes()

        if args.analyze:
            # Analyze query performance
            logger.info("\nAnalyzing query performance...")
            performance = creator.analyze_query_performance()

            if performance["executionTimeMillis"] > 100:
                logger.warning("Query is slow! Consider optimizing indexes.")
            else:
                logger.info("Query performance is good.")

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        creator.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())