"""MongoDB connection and database operations.

This module provides optimized database queries using aggregation pipelines
and bulk operations to avoid N+1 query patterns.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from bson import ObjectId

from ..config.settings import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages MongoDB connection and provides optimized query methods."""

    def __init__(self, config: DatabaseConfig):
        """Initialize database connection.

        Args:
            config: Database configuration settings
        """
        self.config = config
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self) -> bool:
        """Establish connection to MongoDB.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = MongoClient(
                self.config.uri,
                serverSelectionTimeoutMS=self.config.timeout_ms
            )

            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.config.database_name]

            logger.info(f"Connected to MongoDB: {self.config.database_name}")
            return True

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    def get_claims_optimized(
        self,
        claim_ids: Optional[List[str]] = None,
        client_id: Optional[str] = None,
        date_range: Optional[tuple] = None,
        statuses: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get claims with all related data using aggregation pipeline.

        This method uses MongoDB aggregation to join all related collections
        in a single query, avoiding N+1 query patterns.

        Args:
            claim_ids: Specific claim IDs to retrieve
            client_id: Filter by client ID
            date_range: Tuple of (start_date, end_date) strings
            statuses: List of claim statuses to include
            limit: Maximum number of claims to return

        Returns:
            List of claims with embedded related data
        """
        pipeline = []

        # Build match stage
        match_conditions = {}

        if claim_ids:
            # For claim_detail collection, use claim_id field (string)
            match_conditions["claim_id"] = {"$in": claim_ids}

        if client_id:
            match_conditions["client_id"] = client_id

        if statuses:
            match_conditions["status"] = {"$in": statuses}

        if date_range and len(date_range) == 2:
            match_conditions["trans_date"] = {
                "$gte": date_range[0],
                "$lte": date_range[1]
            }

        if match_conditions:
            pipeline.append({"$match": match_conditions})

        # Add limit if specified
        if limit:
            pipeline.append({"$limit": limit})

        # Lookup patient data - use claim_number field directly in claim_detail
        pipeline.append({
            "$lookup": {
                "from": self.config.patient_collection,
                "let": {"claim_num": "$claim_number"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$claim_number", "$$claim_num"]}}},
                    {"$limit": 1}  # Only take first patient record to avoid duplicates
                ],
                "as": "patient_data"
            }
        })

        # Unwind patient data (expecting one patient per claim)
        pipeline.append({
            "$unwind": {
                "path": "$patient_data",
                "preserveNullAndEmptyArrays": True
            }
        })

        # Lookup client data
        pipeline.append({
            "$lookup": {
                "from": self.config.client_collection,
                "let": {"client_id": "$client_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$client_id", "$$client_id"]}}}
                ],
                "as": "client_data"
            }
        })

        # Unwind client data
        pipeline.append({
            "$unwind": {
                "path": "$client_data",
                "preserveNullAndEmptyArrays": True
            }
        })

        # Lookup pharmacy NPI data
        pipeline.append({
            "$lookup": {
                "from": self.config.npi_collection,
                "let": {"pharmacy_npi": "$pharmacy_npi"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$npi", "$$pharmacy_npi"]}}}
                ],
                "as": "pharmacy_npi_data"
            }
        })

        # Unwind pharmacy NPI
        pipeline.append({
            "$unwind": {
                "path": "$pharmacy_npi_data",
                "preserveNullAndEmptyArrays": True
            }
        })

        # Lookup prescriber NPI data
        pipeline.append({
            "$lookup": {
                "from": self.config.npi_collection,
                "let": {"doctor_no": "$doctor_no"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$npi", "$$doctor_no"]}}}
                ],
                "as": "prescriber_npi_data"
            }
        })

        # Unwind prescriber NPI
        pipeline.append({
            "$unwind": {
                "path": "$prescriber_npi_data",
                "preserveNullAndEmptyArrays": True
            }
        })

        try:
            collection = self.db[self.config.claim_collection]
            results = list(collection.aggregate(pipeline))
            logger.info(f"Retrieved {len(results)} claims with related data")
            return results

        except OperationFailure as e:
            logger.error(f"MongoDB aggregation failed: {e}")
            return []

        except Exception as e:
            logger.error(f"Unexpected error in aggregation: {e}")
            return []

    def get_claims_by_ids(self, claim_ids: List[str]) -> List[Dict[str, Any]]:
        """Get claims by specific IDs.

        Args:
            claim_ids: List of claim IDs (as strings)

        Returns:
            List of claim documents
        """
        if not claim_ids:
            return []

        try:
            collection = self.db[self.config.claim_collection]
            # Use claim_id field as string
            claims = list(collection.find({"claim_id": {"$in": claim_ids}}))
            logger.info(f"Retrieved {len(claims)} claims by IDs")
            return claims

        except Exception as e:
            logger.error(f"Error retrieving claims by IDs: {e}")
            return []

    def get_all_related_data(
        self,
        claim_numbers: List[str],
        client_ids: List[str],
        npi_numbers: List[str]
    ) -> Dict[str, Dict]:
        """Fetch all related data in bulk queries.

        Args:
            claim_numbers: List of claim numbers for patient lookup
            client_ids: List of client IDs
            npi_numbers: List of NPI numbers for provider lookup

        Returns:
            Dictionary with 'patients', 'clients', and 'providers' data
        """
        result = {
            'patients': {},
            'clients': {},
            'providers': {}
        }

        try:
            # Get patients by claim numbers (single query)
            if claim_numbers:
                patient_coll = self.db[self.config.patient_collection]
                patients = patient_coll.find({"claim_number": {"$in": claim_numbers}})
                for patient in patients:
                    result['patients'][patient.get('claim_number')] = patient

            # Get clients by IDs (single query)
            if client_ids:
                client_coll = self.db[self.config.client_collection]
                clients = client_coll.find({"client_id": {"$in": client_ids}})
                for client in clients:
                    result['clients'][str(client.get('client_id'))] = client

            # Get NPI providers (single query)
            if npi_numbers:
                npi_coll = self.db[self.config.npi_collection]
                providers = npi_coll.find({"npi": {"$in": npi_numbers}})
                for provider in providers:
                    result['providers'][str(provider.get('npi'))] = provider

            logger.info(
                f"Retrieved related data - "
                f"Patients: {len(result['patients'])}, "
                f"Clients: {len(result['clients'])}, "
                f"Providers: {len(result['providers'])}"
            )

            return result

        except Exception as e:
            logger.error(f"Error fetching related data: {e}")
            return result

    def validate_collections(self) -> bool:
        """Validate that all required collections exist.

        Returns:
            True if all collections exist, False otherwise
        """
        required_collections = [
            self.config.claim_collection,
            self.config.patient_collection,
            self.config.client_collection,
            self.config.npi_collection
        ]

        try:
            existing_collections = self.db.list_collection_names()

            missing = [c for c in required_collections if c not in existing_collections]

            if missing:
                logger.error(f"Missing required collections: {missing}")
                return False

            logger.info("All required collections validated")
            return True

        except Exception as e:
            logger.error(f"Error validating collections: {e}")
            return False