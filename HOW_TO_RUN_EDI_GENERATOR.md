# How to Execute EDI 837 Generator Script

## Prerequisites

1. **Start MongoDB Port Forwarding** (Required)
   ```bash
   kubectl port-forward mongo-0 27018:27017
   ```
   Keep this running in a separate terminal window.

2. **Verify MongoDB Connection**
   The script will automatically connect to: `mongodb://localhost:27018`

## Running the Script

### Basic Usage

Navigate to the project directory and run:
```bash
cd /Users/michaelorourke/Dev/script_logic_edi
python3 process_mongo_to_edi.py [BILLING_DATE] [OPTIONS]
```

### Required Parameter

- `BILLING_DATE`: Date to process in format `YYYY-MM-DD` or `YYYYMMDD`
  - Example: `2026-02-01` or `20260201`

### Optional Parameters

- `--group-id [GROUP_ID]`: Group ID to filter by (default: SLMIA)
- `--mongo-uri [URI]`: Custom MongoDB URI (default: mongodb://localhost:27018)
- `--output-dir [DIR]`: Output directory (default: 837_output)
- `--limit [NUMBER]`: Limit number of claims to process (for testing)

## Examples

### Process SLMIA claims for February 1, 2026
```bash
python3 process_mongo_to_edi.py 2026-02-01
```

### Process different group for specific date
```bash
python3 process_mongo_to_edi.py 2026-02-01 --group-id DIFFERENT_GROUP
```

### Process with limited claims (testing)
```bash
python3 process_mongo_to_edi.py 2026-02-01 --limit 10
```

### Process with custom output directory
```bash
python3 process_mongo_to_edi.py 2026-02-01 --output-dir /path/to/output
```

## Output

The script generates an EDI 837 file with naming pattern:
```
837_mongo_[GROUP_ID]_[BILLING_DATE]_[TIMESTAMP].txt
```

Example: `837_mongo_SLMIA_20260201_20260201_124302.txt`

## Troubleshooting

1. **Connection Error**: Ensure `kubectl port-forward` is running
2. **No Claims Found**: Check if billing date has data in MongoDB
3. **Permission Error**: Ensure output directory is writable

## Full Command Example

```bash
# Terminal 1: Start port forwarding
kubectl port-forward mongo-0 27018:27017

# Terminal 2: Run the script
cd /Users/michaelorourke/Dev/script_logic_edi
python3 process_mongo_to_edi.py 2026-02-01 --group-id SLMIA
```