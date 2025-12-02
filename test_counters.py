#!/usr/bin/env python3
"""Test script to verify counter incrementation in EDI generation."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edi_generator.utils.counter_manager import EDICounterManager

def test_counter_incrementation():
    """Test that only interchange counter increments."""
    print("\n" + "=" * 60)
    print("Testing EDI Counter Incrementation")
    print("=" * 60)

    # Initialize counter manager
    counter_mgr = EDICounterManager()

    # Get initial values
    initial = counter_mgr.get_current_values()
    print(f"\nInitial values:")
    print(f"  Interchange: {initial['interchange_control_number']:09d}")
    print(f"  Group:       4 (static)")
    print(f"  Transaction: 0001 (static)")

    # Get next values (simulating EDI generation)
    print(f"\nSimulating EDI generation...")
    interchange1 = counter_mgr.get_next_interchange_number()
    group1 = counter_mgr.get_next_group_number()
    trans1 = counter_mgr.get_transaction_number()

    print(f"\nFirst generation:")
    print(f"  Interchange: {interchange1} (was {initial['interchange_control_number']:09d})")
    print(f"  Group:       {group1} (static)")
    print(f"  Transaction: {trans1} (static)")

    # Simulate second generation
    interchange2 = counter_mgr.get_next_interchange_number()
    group2 = counter_mgr.get_next_group_number()
    trans2 = counter_mgr.get_transaction_number()

    print(f"\nSecond generation:")
    print(f"  Interchange: {interchange2}")
    print(f"  Group:       {group2} (static)")
    print(f"  Transaction: {trans2} (static)")

    # Get final values
    final = counter_mgr.get_current_values()
    print(f"\nFinal stored values (ready for next generation):")
    print(f"  Interchange: {final['interchange_control_number']:09d}")

    # Verify values
    assert len(interchange1) == 9, f"Interchange must be 9 chars, got {len(interchange1)}"
    assert len(interchange2) == 9, f"Interchange must be 9 chars, got {len(interchange2)}"
    assert group1 == "4", f"Group must be '4', got {group1}"
    assert group2 == "4", f"Group must be '4', got {group2}"
    assert trans1 == "0001", f"Transaction must be '0001', got {trans1}"
    assert trans2 == "0001", f"Transaction must be '0001', got {trans2}"

    # Verify only interchange increments
    assert int(interchange2) == int(interchange1) + 1, "Interchange should increment"

    print(f"\n✅ All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_counter_incrementation()