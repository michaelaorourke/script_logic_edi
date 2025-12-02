# MongoDB-Based EDI 837 Processing

## Overview

The EDI 837 generator now supports direct MongoDB queries as a data source, replacing the need for CSV exports. This allows for real-time EDI generation from the production database.

## New Files Created

### `process_mongo_to_edi.py`
Main script for MongoDB-based EDI generation. Replaces `process_csv_to_edi.py` for database-driven workflows.

### `test_mongo_billing.py`
Utility script to test MongoDB connection and inspect billing_date field formats.

## Key Changes

### 1. Data Source
- **Before**: Read from CSV file (`scriptlogic.claim_detail_120125.csv`)
- **After**: Query MongoDB `claim_detail` collection directly

### 2. Query Filters
- `billing_date`: Accepts as CLI argument (format: YYYY-MM-DD or YYYYMMDD)
- `group_id`: Defaults to "SLMIA" (configurable via `--group-id`)

### 3. MongoDB Connection
- Supports port forwarding (default: port 27018)
- Configurable via `--mongo-uri` argument
- Uses existing `DatabaseConnection` class from `edi_generator.database.connection`

## Usage

### Basic Usage (with port forwarding on 27018)
```bash
python3 process_mongo_to_edi.py 2025-12-01
```

### With Custom Group ID
```bash
python3 process_mongo_to_edi.py 2025-12-01 --group-id CUSTOM_GROUP
```

### With Custom MongoDB URI
```bash
python3 process_mongo_to_edi.py 2025-12-01 --mongo-uri "mongodb://localhost:27017/"
```

### With Limit (for testing)
```bash
python3 process_mongo_to_edi.py 2025-12-01 --limit 10
```

### Full Example
```bash
python3 process_mongo_to_edi.py 2025-12-01 \
  --group-id SLMIA \
  --mongo-uri "mongodb://localhost:27018/?directConnection=true" \
  --output-dir 837_output \
  --limit 50
```

## MongoDB Query Details

### Collection Schema
The `claim_detail` collection uses:
- `billing_date`: BSON DateTime field
- `group_id`: String field

### Query Filter Used
```python
{
    "group_id": "SLMIA",  # Or provided group_id
    "billing_date": {
        "$gte": start_of_day,  # 2025-12-01 00:00:00
        "$lt": end_of_day      # 2025-12-02 00:00:00
    }
}
```

### Field Mapping
MongoDB fields are mapped to the EDI claim format:
- `claim_id` → `claim_id` (converted to string)
- `claim_number` → `claim_number`
- `billing_date` → (used for filtering only)
- `trans_date` → `trans_date` (converted to YYYYMMDD)
- `rx_date` → `rx_date` (converted to YYYYMMDD)
- All pricing fields preserved as floats

## Configuration

### Constants (in `process_mongo_to_edi.py`)
```python
GROUP_ID = "SLMIA"       # Default group ID
DEFAULT_PORT = 27018     # Port forwarding port
```

### Environment-Specific Settings
- **Production**: Use port forwarding on 27018
- **Local Dev**: Use standard MongoDB port 27017
- **Custom**: Provide full MongoDB URI

## Testing

### Test MongoDB Connection
```bash
python3 test_mongo_billing.py
```

This will show:
- Connection status
- Document counts
- Sample billing_date values and types
- Available group_ids

### Validate Output
Compare MongoDB-generated EDI with CSV version:
```bash
# Generate from MongoDB
python3 process_mongo_to_edi.py 2025-12-01

# Validate against CSV
python3 validate_edi_data.py 837_output/837_mongo_*.txt scriptlogic.claim_detail_120125.csv
```

## Output Files

Files are generated with the naming pattern:
```
837_output/837_mongo_{GROUP_ID}_{BILLING_DATE}_{TIMESTAMP}.txt
```

Example:
```
837_output/837_mongo_SLMIA_20251201_20251202_102054.txt
```

## Performance

- MongoDB query time: ~200-400ms for 80 claims
- Transformation time: <100ms
- EDI generation: ~2-5ms
- Total processing time: <1 second for typical batch

## Error Handling

The script handles:
- Connection failures with clear error messages
- Missing billing_date values (logged as warnings)
- Various date formats (YYYY-MM-DD, YYYYMMDD, MM/DD/YYYY)
- Empty result sets (exits gracefully)

## Migration Path

To migrate from CSV to MongoDB processing:

1. **Test connection**: Run `test_mongo_billing.py`
2. **Test with limit**: Run with `--limit 5` to verify data
3. **Full test**: Process full billing date
4. **Validate**: Compare with CSV output using validation scripts
5. **Production**: Remove CSV dependency

## Benefits

- **Real-time data**: No need for CSV exports
- **Filtering**: Built-in support for date and group filtering
- **Scalability**: Can process any date range
- **Consistency**: Uses same EDI generator as CSV version
- **Auditability**: Clear logging of queries and results