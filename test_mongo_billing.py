#!/usr/bin/env python3
"""Test MongoDB connection and check billing_date field format."""

import sys
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient

# Test configuration
MONGO_URI = "mongodb://localhost:27018/?directConnection=true"
DB_NAME = "scriptlogic"
COLLECTION_NAME = "claim_detail"
GROUP_ID = "SLMIA"


def main():
    """Test MongoDB connection and examine billing_date field."""

    print(f"Connecting to MongoDB at {MONGO_URI}")

    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")

        # Get collection stats
        count = collection.count_documents({})
        print(f"Total documents in {COLLECTION_NAME}: {count:,}")

        # Check documents with group_id = SLMIA
        slmia_count = collection.count_documents({"group_id": GROUP_ID})
        print(f"Documents with group_id='{GROUP_ID}': {slmia_count:,}")

        # Get a sample document with SLMIA group_id
        sample = collection.find_one({"group_id": GROUP_ID})

        if sample:
            print("\nSample document fields:")
            print(f"  - billing_date: {sample.get('billing_date')} (type: {type(sample.get('billing_date'))})")
            print(f"  - group_id: {sample.get('group_id')}")
            print(f"  - claim_number: {sample.get('claim_number')}")
            print(f"  - client_name: {sample.get('client_name')}")

            # Check distinct billing_date values
            print("\nDistinct billing_date values (first 10):")
            distinct_dates = collection.distinct("billing_date", {"group_id": GROUP_ID})[:10]
            for date_val in distinct_dates:
                print(f"  - {date_val} (type: {type(date_val)})")

            # If billing_date is a datetime, show date range
            if isinstance(sample.get('billing_date'), datetime):
                # Get min and max dates
                pipeline = [
                    {"$match": {"group_id": GROUP_ID}},
                    {"$group": {
                        "_id": None,
                        "min_date": {"$min": "$billing_date"},
                        "max_date": {"$max": "$billing_date"}
                    }}
                ]
                result = list(collection.aggregate(pipeline))
                if result:
                    print(f"\nDate range for {GROUP_ID}:")
                    print(f"  - Earliest: {result[0]['min_date']}")
                    print(f"  - Latest: {result[0]['max_date']}")

            # Count by billing_date (show top 5)
            print("\nClaim counts by billing_date (top 5):")
            pipeline = [
                {"$match": {"group_id": GROUP_ID}},
                {"$group": {
                    "_id": "$billing_date",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]

            for item in collection.aggregate(pipeline):
                print(f"  - {item['_id']}: {item['count']} claims")

        else:
            print(f"\nNo documents found with group_id='{GROUP_ID}'")

            # Show available group_ids
            print("\nAvailable group_ids (first 10):")
            distinct_groups = collection.distinct("group_id")[:10]
            for group in distinct_groups:
                count = collection.count_documents({"group_id": group})
                print(f"  - {group}: {count} documents")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    finally:
        if 'client' in locals():
            client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())