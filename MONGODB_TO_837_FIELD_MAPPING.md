# MongoDB to 837 EDI Field Mapping Documentation

## Overview
This document provides a comprehensive mapping of MongoDB `claim_detail` collection fields to their corresponding 837 Professional (837P) EDI segments and elements. The system processes pharmacy claims data from MongoDB and generates compliant X12 837 EDI files for healthcare claim submission.

## Database Source
- **Collection**: `claim_detail`
- **Database**: MongoDB (typically accessed via port 27018)
- **Query Filters**:
  - `group_id` (e.g., "SLMIA" for Midwestern Insurance Alliance)
  - `billing_date` (date range query)

## Field Mappings

### Patient Information
These fields contain patient demographic and identification data.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `first_name` | NM1*QC | NM104 | Patient first name | Direct mapping |
| `last_name` | NM1*QC | NM103 | Patient last name | Direct mapping |
| `dob` | DMG | DMG02 | Patient date of birth | Convert ISO to YYYYMMDD |
| `ssno` | - | - | Social Security Number | Used to derive gender (odd last digit=M, even=F) |
| `patient_address` | N3 | N301 | Patient street address | Parse first part before comma |
| `patient_address` | N4 | N401, N402 | Patient city, state | Parse parts after commas |
| `date_of_injury` | DMG | DMG02 | Date of injury | Convert ISO to YYYYMMDD |
| `date_of_injury` | DTP*439 | DTP03 | Accident date | Convert ISO to YYYYMMDD |
| `claim_number` | REF*Y4 | REF02 | Workers comp claim number | Direct mapping |
| `claim_number` | CLM | CLM01 | Claim identifier | Direct mapping |

### Client/Subscriber/Payer Information
These fields identify the insurance payer and subscriber.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `client_name` | NM1*IL | NM103 | Subscriber/client name | Direct mapping |
| `client_name` | NM1*PR | NM103 | Payer name | Direct mapping |
| `client_id` | - | - | Client identifier | Internal reference only |
| `client_address` | N3 | N301 | Payer street address | Parse first part before comma |
| `client_address` | N4 | N401 | Payer city | Parse second part |
| `client_address` | N4 | N402 | Payer state | Parse third part, take first 2 chars |
| - | N4 | N403 | Payer zip | Default: "40253" if not available |

### Pharmacy/Service Facility Information
These fields identify where the prescription was filled.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `pharmacy_npi` | NM1*77 | NM109 | Service facility NPI | Direct mapping |
| `pharmacy_npi` | REF*D9 | REF02 | Part of claim reference | Combined with other fields |
| `pharmacy` | NM1*77 | NM103 | Pharmacy organization name | Direct mapping |
| `pharmacy_address` | N3 | N301 | Pharmacy street address | If available from lookup |
| `pharmacy_address` | N4 | N401-403 | Pharmacy city, state, zip | If available from lookup |

### Prescriber Information
These fields identify the prescribing physician.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `doctor_no` | NM1*DK | NM109 | Prescriber NPI/ID | Direct mapping |
| `prescriber_name` | NM1*DK | NM103 | Prescriber last name | Parse before comma if present |
| `prescriber_name` | NM1*DK | NM104 | Prescriber first name | Parse after comma if present |

### Prescription/Service Line Details
These fields contain the core prescription and drug information.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `trans_date` | DTP*472 | DTP03 | Service date | Convert ISO to YYYYMMDD |
| `trans_date` | REF*D9 | REF02 | Part of claim reference | Combined with NPI and _id |
| `rx_date` | K3 NCPDP | Pos 62-69 | Prescription written date | Convert to MMDDYYYY format |
| `rx_no` | REF*6R | REF02 | Prescription number | Direct mapping |
| `drug_name` | SV1 | SV101-7 | Drug description | Direct mapping |
| `ndc` | LIN | LIN03 | National Drug Code | Direct mapping, qualifier "N4" |
| `quantity` | SV1 | SV104 | Quantity dispensed | Format as decimal |
| `days_supply` | K3 NCPDP | Pos 71-73 | Days supply | Zero-padded to 3 digits |
| `days_supply` | CTP | CTP04 | Days supply | Format as decimal |
| `daw` | K3 NCPDP | Pos 4 | Dispense as Written code | Single digit (0-9) |
| `brand_gen` | K3 NCPDP | Pos 74 | Generic indicator | G=Generic, B=Brand |

### Financial/Pricing Fields
These fields contain cost and payment information.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `u_and_c` | HCP | HCP03 | Usual & customary charge | Format as decimal (2 places) |
| `plan_paid` | CLM | CLM02 | Total claim charge amount | Format as decimal, fallback for fee_schedule |
| `plan_paid` | SV1 | SV102 | Line item charge | Format as decimal |
| `fee_schedule` | HCP | HCP05 | Fee schedule amount | Format as decimal |
| `fee_schedule` | CLM | CLM02 | Claim amount (if available) | Primary source for claim amount |
| `member_paid` | HCP | HCP02 | Amount due/copay | Fallback for due_amount |
| `due_amount` | HCP | HCP02 | Amount due from payer | Format as decimal |

### System/Control Fields
These fields are used for internal tracking and filtering.

| MongoDB Field | 837 Segment | Element | Description | Format/Transformation |
|--------------|------------|---------|-------------|----------------------|
| `_id` | REF*D9 | REF02 | MongoDB ObjectId | Extract $oid if present, combine in reference |
| `group_id` | - | - | Query filter | Used to select claims (e.g., "SLMIA") |
| `billing_date` | - | - | Query filter | Used to select date range |
| `subscriber_num` | - | - | Alternative claim ID | Fallback if claim_number not present |
| `status` | - | - | Claim status | Not directly mapped to EDI |

## Special Segments

### K3 Segment - NCPDP Format
The K3 segment contains pharmacy-specific data in a fixed 80-character format:

| Position | Length | Field | MongoDB Source | Description |
|----------|--------|-------|----------------|-------------|
| 1-2 | 2 | Fill Number | - | Default "00" for original fill |
| 3 | 1 | (Space) | - | Required space |
| 4 | 1 | DAW Code | `daw` | Dispense as Written (0-9) |
| 5-41 | 37 | (Spaces) | - | Reserved spaces |
| 42-43 | 2 | Basis of Cost | - | Default "01" (AWP) |
| 44-61 | 18 | (Spaces) | - | Reserved spaces |
| 62-69 | 8 | Prescription Date | `rx_date` | Format: MMDDYYYY |
| 70 | 1 | (Space) | - | Required space |
| 71-73 | 3 | Days Supply | `days_supply` | Zero-padded to 3 digits |
| 74 | 1 | Generic Flag | `brand_gen` | G=Generic, B=Brand |
| 75-80 | 6 | (Spaces) | - | Reserved spaces |

### REF*D9 - Claim Reference Identifier
Constructed from multiple fields (max 50 characters):
- Transaction date (YYYYMMDD format)
- Pharmacy NPI
- MongoDB ObjectId (if available)

## Data Transformations

### Date Conversions
- **ISO to YYYYMMDD**: Remove time component, remove hyphens
- **ISO to MMDDYYYY**: Reformat for K3 segment prescription date
- **ISO to YYMMDD**: Used for ISA segment date

### Address Parsing
Patient and client addresses are stored as comma-separated strings:
1. Street address: Everything before first comma
2. City: Text between first and second comma (trimmed)
3. State: First 2 characters after second comma (trimmed)
4. Zip: Default values used if not available

### Gender Derivation
Gender is derived from SSN when not explicitly provided:
- Odd last digit = Male (M)
- Even last digit = Female (F)

### Name Parsing
Prescriber names may be in "LastName, FirstName" format:
- If comma present: Split and assign to last/first
- If no comma: Entire string used as last name

## Default Values

| Field | Default Value | Used When |
|-------|--------------|-----------|
| Patient Zip | "00000" | Address zip not available |
| Payer State | "KY" | Client state not parsed |
| Payer Zip | "40253" | Client zip not available |
| Fill Number | "00" | Original prescription |
| Basis of Cost | "01" | AWP pricing basis |
| DAW Code | "0" | No DAW specified |
| Generic Flag | "G" | When brand_gen not specified |

## Segment Hierarchy

The 837 file follows a strict hierarchical structure:

1. **Interchange Level**
   - ISA/IEA segments

2. **Functional Group Level**
   - GS/GE segments

3. **Transaction Set Level**
   - ST/SE segments
   - BHT (Beginning of Transaction)

4. **Information Source Level (2000A)**
   - HL*1 (Billing Provider)
   - 2010AA segments (Provider details)

5. **Subscriber Level (2000B)**
   - HL*2 (Subscriber)
   - 2010BA (Subscriber info)
   - 2010BB (Payer info)

6. **Patient Level (2000C)**
   - HL*3 (Patient)
   - 2010CA (Patient demographics)

7. **Claim Level (2300)**
   - CLM (Claim information)
   - HI (Diagnosis codes)
   - HCP (Pricing at claim level)
   - 2310C (Service facility/Pharmacy)

8. **Service Line Level (2400)**
   - LX (Line counter)
   - SV1 (Professional service)
   - DTP (Service dates)
   - REF (Line item references)
   - K3 (NCPDP data)
   - HCP (Line level pricing)
   - LIN (Drug identification)
   - CTP (Drug quantity)
   - 2310B (Prescriber)

## Notes

1. **Dynamic Control Numbers**: ISA13, GS06, and ST02 use incrementing control numbers managed by EDICounterManager
2. **Claim Grouping**: Multiple prescriptions for the same claim_number are grouped under a single patient hierarchy
3. **Embedded Lookups**: The system supports embedded NPI data lookups but falls back to direct field values
4. **Validation**: All segments are validated for proper length and format, especially ISA (106 chars) and K3 (80 chars)
5. **Character Limits**: Field values are truncated to meet X12 specifications for maximum element lengths