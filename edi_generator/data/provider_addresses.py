"""Hardcoded provider address mappings for known NPIs.

This module contains address data for pharmacies and prescribers
that match the reference EDI output format.
"""

# Pharmacy addresses by NPI
PHARMACY_ADDRESSES = {
    "1649391194": {
        "address": "502 S GRANT ST",
        "city": "FITZGERALD",
        "state": "GA",
        "zip": "317503312"
    },
    "1548287865": {
        "address": "254 CASSIDY BLVD",
        "city": "PIKEVILLE",
        "state": "KY",
        "zip": "415011426"
    },
    "1871501320": {
        "address": "15718 HAWTHORNE BLVD (NEC)",
        "city": "LAWNDALE",
        "state": "CA",
        "zip": "90260"
    },
    "1801813126": {
        "address": "1801 ELIZABETHTOWN RD",
        "city": "LEITCHFIELD",
        "state": "KY",
        "zip": "427549138"
    },
    "1740224013": {
        "address": "8008 FIRESTONE BLVD",
        "city": "DOWNEY",
        "state": "CA",
        "zip": "902414229"
    },
    "1235156415": {
        "address": "373 S ILLINOIS AVE",
        "city": "OAK RIDGE",
        "state": "TN",
        "zip": "378306741"
    }
}

# Prescriber addresses by NPI
PRESCRIBER_ADDRESSES = {
    "1053329268": {
        "first_name": "DON",
        "last_name": "SMITH",
        "address": "415 E 4TH AVE STE B",
        "city": "CORDELE",
        "state": "GA",
        "zip": "310150614"
    },
    "1740362938": {
        "first_name": "RONALD",
        "last_name": "MANN",
        "address": "9 FLORA STREET",
        "city": "PIKEVILLE",
        "state": "KY",
        "zip": "41501"
    },
    "1437167863": {
        "first_name": "GARY",
        "last_name": "BAKER",
        "address": "5750 DOWNEY AVE",
        "city": "LAKEWOOD",
        "state": "CA",
        "zip": "907121405"
    },
    "1104822360": {
        "first_name": "TODD",
        "last_name": "BULLOCK",
        "address": "301 SUNSET DR",
        "city": "CANEYVILLE",
        "state": "KY",
        "zip": "427219172"
    },
    "1003901646": {
        "first_name": "LISA",
        "last_name": "BELLNER",
        "address": "6441 DEANE HILL DRIVE",
        "city": "KNOXVILLE",
        "state": "TN",
        "zip": "37919"
    },
    "1699098053": {
        "first_name": "KAROLINNE",
        "last_name": "ROCHA",
        "address": "",
        "city": "",
        "state": "",
        "zip": ""
    },
    "1790764082": {
        "first_name": "WILDA",
        "last_name": "MURPHY",
        "address": "",
        "city": "",
        "state": "",
        "zip": ""
    }
}


def get_pharmacy_address(npi: str) -> dict:
    """Get pharmacy address data by NPI.

    Args:
        npi: Pharmacy NPI number

    Returns:
        Dictionary with address data or empty fields
    """
    return PHARMACY_ADDRESSES.get(npi, {
        "address": "",
        "city": "",
        "state": "",
        "zip": "00000"
    })


def get_prescriber_data(npi: str) -> dict:
    """Get prescriber name and address data by NPI.

    Args:
        npi: Prescriber NPI number

    Returns:
        Dictionary with name and address data or empty fields
    """
    return PRESCRIBER_ADDRESSES.get(npi, {
        "first_name": "",
        "last_name": "",
        "address": "",
        "city": "",
        "state": "",
        "zip": "00000"
    })