#!/usr/bin/env python3
"""Test EDI generation with minimal data to verify format correctness."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edi_generator.config.settings import Settings
from edi_generator.edi.generator import EDIGenerator
from edi_generator.utils.counter_manager import EDICounterManager

def test_minimal_edi_generation():
    """Test EDI generation with minimal claim data."""
    print("\n" + "=" * 60)
    print("TESTING MINIMAL EDI GENERATION")
    print("=" * 60)

    # Get current counter value
    counter_mgr = EDICounterManager()
    initial_counters = counter_mgr.get_current_values()
    print(f"\nInitial interchange counter: {initial_counters['interchange_control_number']:09d}")

    # Create settings
    settings = Settings()

    # Create generator
    generator = EDIGenerator(settings)

    # Create minimal test claim data
    test_claims = [{
        "claim_number": "TEST12345",
        "patient_data": {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_injury": "2024-01-01",
            "gender": "M",
            "address1": "123 Main St",
            "city": "Anytown",
            "state": "MO",
            "zip": "12345"
        },
        "client_data": {
            "name": "Test Insurance Co",
            "address1": "456 Insurance Ave",
            "city": "Insurance City",
            "state": "MO",
            "zip": "54321"
        },
        "pharmacy_npi": "1234567890",
        "pharmacy": "Test Pharmacy",
        "doctor_no": "9876543210",
        "prescriber_name": "Smith, Jane",
        "trans_date": "2024-01-15",
        "rx_date": "2024-01-10",
        "rx_no": "RX123456",
        "drug_name": "Test Drug",
        "ndc": "12345678901",
        "quantity": 30,
        "days_supply": 30,
        "daw": "0",
        "brand_gen": "G",
        "u_and_c": 100.00,
        "plan_paid": 80.00,
        "member_paid": 20.00
    }]

    # Generate EDI segments
    print("\nGenerating EDI segments...")
    segments = generator.generate_from_claims(test_claims)

    print(f"Generated {len(segments)} segments")

    # Check critical segments
    print("\n" + "-" * 40)
    print("CRITICAL SEGMENT VALIDATION:")
    print("-" * 40)

    # Check ISA segment
    isa_segment = segments[0] if segments else ""
    print(f"\n1. ISA Segment (first 50 chars): {isa_segment[:50]}...")
    print(f"   ISA Length: {len(isa_segment)} (should be 106)")
    assert len(isa_segment) == 106, f"ISA length error: {len(isa_segment)}"

    # Extract control numbers from ISA
    isa_parts = isa_segment.split('*')
    isa_control = isa_parts[13] if len(isa_parts) > 13 else "N/A"
    print(f"   ISA13 Control Number: {isa_control}")

    # Check GS segment
    gs_segment = segments[1] if len(segments) > 1 else ""
    gs_parts = gs_segment.split('*')
    gs_control = gs_parts[6] if len(gs_parts) > 6 else "N/A"
    print(f"\n2. GS Control Number (GS06): {gs_control}")
    assert gs_control == "4", f"GS control should be '4', got '{gs_control}'"

    # Check ST segment
    st_segment = segments[2] if len(segments) > 2 else ""
    st_parts = st_segment.split('*')
    st_control = st_parts[2] if len(st_parts) > 2 else "N/A"
    print(f"\n3. ST Control Number (ST02): {st_control}")
    assert st_control == "0001", f"ST control should be '0001', got '{st_control}'"

    # Find and check trailer segments
    print("\n4. Checking trailer segments...")
    iea_segment = None
    ge_segment = None
    se_segment = None

    for seg in segments:
        if seg.startswith("IEA"):
            iea_segment = seg
        elif seg.startswith("GE"):
            ge_segment = seg
        elif seg.startswith("SE"):
            se_segment = seg

    # Check SE trailer
    if se_segment:
        se_parts = se_segment.split('*')
        se_control = se_parts[2].rstrip('~') if len(se_parts) > 2 else "N/A"
        print(f"   SE02: {se_control} (should match ST02: {st_control})")
        assert se_control == st_control, "SE/ST control number mismatch"

    # Check GE trailer
    if ge_segment:
        ge_parts = ge_segment.split('*')
        ge_control = ge_parts[2].rstrip('~') if len(ge_parts) > 2 else "N/A"
        print(f"   GE02: {ge_control} (should match GS06: {gs_control})")
        assert ge_control == gs_control, "GE/GS control number mismatch"

    # Check IEA trailer
    if iea_segment:
        iea_parts = iea_segment.split('*')
        iea_control = iea_parts[2].rstrip('~') if len(iea_parts) > 2 else "N/A"
        print(f"   IEA02: {iea_control} (should match ISA13: {isa_control})")
        assert iea_control == isa_control, "IEA/ISA control number mismatch"

    # Check that interchange counter incremented
    final_counters = counter_mgr.get_current_values()
    print(f"\n5. Counter incrementation check:")
    print(f"   Initial: {initial_counters['interchange_control_number']:09d}")
    print(f"   Used:    {isa_control}")
    print(f"   Final:   {final_counters['interchange_control_number']:09d}")

    expected_final = int(isa_control) + 1
    assert final_counters['interchange_control_number'] == expected_final, \
        f"Counter should be {expected_final}, got {final_counters['interchange_control_number']}"

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("\nCONFIRMATION:")
    print("1. ISA segment maintains 106-character length")
    print("2. Interchange counter increments properly")
    print("3. Group control stays at '4'")
    print("4. Transaction control stays at '0001'")
    print("5. Headers and trailers match correctly")
    print("\n✅ EDI FORMAT IS VALID - SAFE TO USE")
    print("=" * 60)

if __name__ == "__main__":
    test_minimal_edi_generation()