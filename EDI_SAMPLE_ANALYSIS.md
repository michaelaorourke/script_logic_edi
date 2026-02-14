# EDI 837 Sample Data Analysis and Mapping

## Raw EDI Sample
```
Jeryd Colson Available~N4*Unknown*XX*00000~HL*24*1*22*1~SBR*P********WC~NM1*IL*2*Midwestern Insurance Alliance~NM1*PR*2*Midwestern Insurance Alliance*****PI*CB691~N3*Address Not Available~N4*Louisville*KY*40253~HL*25*24*23*0~PAT*20~NM1*QC*1*COLSON*JERYD~N3*Address Not Available~N4*Greensburg*IN*00000~DMG*D8*20250326*F~REF*Y4*MP20250402003~REF*SY*999999999~CLM*MP20250402003*52.32***01:B:1*Y*A*Y*Y**EM~DTP*439*D8*20250326~REF*D9*2025121712352329196944dce1c0c5bf138ecebd7d~K3*RX~HI*ABK:R52~HCP*10*29.77*31.59*852631493*52.32~NM1*77*2*None*****XX*1235232919~N3*Address Not Available~N4*Unknown*XX*00000~LX*1~SV1*HC:99070:::::Methocarbamol Oral Tablet 750 MG*52.32*UN*56.000*11**1~DTP*472*D8*20251217~REF*6R*000002004323~K3*00 0
```

## Parsed Segments with Data Mapping

### Subscriber Level (2000B)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **HL*24*1*22*1** | Hierarchical Level 24, Parent 1, Subscriber level | System generated | Links to billing provider |
| **SBR*P********WC** | Subscriber relationship: Primary, Workers Comp | Hard-coded values | WC = Workers Compensation |

### Subscriber Name (2010BA)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **NM1*IL*2*Midwestern Insurance Alliance** | Subscriber/Insured organization | `client_name` | Organization entity (2) |

### Payer Name (2010BB)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **NM1*PR*2*Midwestern Insurance Alliance*****PI*CB691** | Payer organization | `client_name` + config payer_id | **DUPLICATE**: Same as subscriber |
| **N3*Address Not Available** | Payer street | Default when `client_address` empty | |
| **N4*Louisville*KY*40253** | Payer city/state/zip | Default values or `client_address` parsed | |

### Patient Level (2000C)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **HL*25*24*23*0** | Hierarchical Level 25, Parent 24, Patient level | System generated | No children (0) |
| **PAT*20** | Patient relationship to subscriber | Hard-coded | 20 = Child |

### Patient Name (2010CA)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **NM1*QC*1*COLSON*JERYD** | Patient name | `last_name`, `first_name` | Person entity (1) |
| **N3*Address Not Available** | Patient street | Default when `patient_address` empty | |
| **N4*Greensburg*IN*00000** | Patient city/state/zip | `patient_address` parsed or defaults | |

### Patient Demographics
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **DMG*D8*20250326*F** | Demographics | `date_of_injury`, gender from `ssno` | Female, DOI: 2025-03-26 |
| **REF*Y4*MP20250402003** | Workers comp claim # | `claim_number` | **DUPLICATE**: Also in CLM01 |
| **REF*SY*999999999** | SSN | Hard-coded default | Not actual SSN |

### Claim Information (2300)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **CLM*MP20250402003*52.32***01:B:1*Y*A*Y*Y**EM** | Claim header | `claim_number`, `fee_schedule` or `plan_paid` | $52.32 total |
| **DTP*439*D8*20250326** | Accident date | `date_of_injury` | **DUPLICATE**: Same as DMG02 |
| **REF*D9*2025121712352329196944dce1c0c5bf138ecebd7d** | Claim reference | `trans_date` + `pharmacy_npi` + `_id` | Composite key |
| **K3*RX** | File type indicator | Hard-coded | Simple K3 |
| **HI*ABK:R52** | Diagnosis code | Hard-coded | R52 = Pain, unspecified |

### Claim Pricing (HCP)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **HCP*10*29.77*31.59*852631493*52.32** | Pricing/Repricing | | |
| - HCP02 | $29.77 | `due_amount` or `member_paid` | Amount due |
| - HCP03 | $31.59 | `u_and_c` | Usual & customary |
| - HCP04 | 852631493 | Config `repricer_id` | |
| - HCP05 | $52.32 | `fee_schedule` or `plan_paid` | **DUPLICATE**: Same as CLM02 |

### Service Facility/Pharmacy (2310C)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **NM1*77*2*None*****XX*1235232919** | Service facility | `pharmacy`, `pharmacy_npi` | Organization entity |
| **N3*Address Not Available** | Facility street | Default when `pharmacy_address` empty | |
| **N4*Unknown*XX*00000** | Facility location | Default values | |

### Service Line (2400)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **LX*1** | Line counter | System generated | First service line |

### Service Details (SV1)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **SV1*HC:99070:::::Methocarbamol Oral Tablet 750 MG*52.32*UN*56.000*11**1** | Service/Drug | | |
| - SV101 | HC:99070 + drug name | Hard-coded + `drug_name` | Procedure code + description |
| - SV102 | $52.32 | `fee_schedule` or `plan_paid` | **DUPLICATE**: Same as CLM02, HCP05 |
| - SV103 | UN | Hard-coded | Unit of measure |
| - SV104 | 56.000 | `quantity` | Quantity dispensed |
| - SV105 | 11 | Hard-coded | Place of service |

### Service Dates and References
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **DTP*472*D8*20251217** | Service date | `trans_date` | Fill date: 2025-12-17 |
| **REF*6R*000002004323** | Prescription # | `rx_no` | |

### NCPDP Data (K3)
| Segment | Data | Source Field Mapping | Notes |
|---------|------|---------------------|-------|
| **K3*00 0...** | NCPDP 80-char | Multiple fields | Truncated in sample |
| - Pos 1-2 | "00" | Hard-coded | Original fill |
| - Pos 4 | "0" | `daw` | DAW code |

## Data Overlaps and Redundancies

### 1. **Claim Number (MP20250402003)**
- Appears in: REF*Y4, CLM01
- Source: `claim_number`
- Purpose: Different contexts (Workers Comp reference vs Claim ID)

### 2. **Date of Injury (20250326)**
- Appears in: DMG02, DTP*439
- Source: `date_of_injury`
- Purpose: Patient demographics vs Accident date
- **Could be deduplicated**

### 3. **Claim Amount ($52.32)**
- Appears in: CLM02, HCP05, SV102
- Source: `fee_schedule` or `plan_paid`
- Purpose: Total claim vs repriced amount vs line charge
- **Required redundancy per X12 spec**

### 4. **Organization Name (Midwestern Insurance Alliance)**
- Appears in: NM1*IL, NM1*PR
- Source: `client_name`
- Purpose: Subscriber vs Payer identification
- **Could use different values if available**

### 5. **Default/Missing Address Values**
- "Address Not Available" appears 3 times (payer, patient, pharmacy)
- "Unknown*XX*00000" appears twice (beginning and pharmacy)
- Shows missing address data in source

## Missing or Defaulted Data

| Field | Default Value | Reason |
|-------|--------------|--------|
| Patient Address | "Address Not Available" | `patient_address` empty/null |
| Patient Zip | "00000" | No zip in `patient_address` |
| Pharmacy Name | "None" | `pharmacy` field empty |
| Pharmacy Address | "Address Not Available" | `pharmacy_address` empty |
| Pharmacy Location | "Unknown*XX*00000" | No pharmacy location data |
| SSN | "999999999" | Privacy/not collected |
| Diagnosis | "R52" | Generic pain code used |

## Key Observations

1. **Workers Compensation Claim**: SBR segment shows "WC" indicating workers comp
2. **Female Patient**: DMG shows "F" for gender
3. **Drug**: Methocarbamol Oral Tablet 750 MG
4. **Quantity**: 56 units dispensed
5. **Pricing Structure**:
   - Total Charge: $52.32
   - U&C Price: $31.59
   - Amount Due: $29.77
6. **Date Discrepancy**:
   - Injury Date: 2025-03-26
   - Service Date: 2025-12-17
   - ~9 months between injury and service

## Data Quality Issues

1. **Missing Addresses**: Multiple segments show "Address Not Available"
2. **Generic Pharmacy Info**: Pharmacy shown as "None" with NPI 1235232919
3. **Truncated K3 Segment**: NCPDP data appears incomplete
4. **Default SSN**: Using placeholder 999999999
5. **Missing Prescriber**: No 2310B segment for prescriber information

## Recommendations

1. **Address Enrichment**: Need better address data for all entities
2. **Pharmacy Lookup**: Should populate actual pharmacy name from NPI
3. **Complete K3 Data**: Ensure full 80-character NCPDP format
4. **Add Prescriber**: Missing prescriber (2310B) segment
5. **Validate Dates**: Large gap between injury and service dates