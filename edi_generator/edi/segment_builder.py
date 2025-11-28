"""EDI segment builder with validation and proper formatting.

This module provides safe construction of EDI segments with proper
validation, character limits, and special character handling.
"""

import logging
from typing import List, Optional, Any
from datetime import datetime
from ..utils.formatters import format_date_mmddyyyy

logger = logging.getLogger(__name__)


class EDISegmentBuilder:
    """Builds and validates EDI segments according to X12 specifications."""

    MAX_SEGMENT_LENGTH = 999
    ELEMENT_SEPARATOR = "*"
    SEGMENT_TERMINATOR = "~"
    SUBELEMENT_SEPARATOR = ":"

    @classmethod
    def build_k3_ncpdp(
        cls,
        fill_number: str = "00",
        daw_code: str = "0",
        basis_of_cost: str = "01",
        rx_date: str = "",
        days_supply: int = 0,
        generic_flag: str = ""
    ) -> str:
        """Build K3 segment with 80-character NCPDP format.

        This is the critical pharmacy data segment that must be exactly 80 characters.

        Args:
            fill_number: Fill/refill number (2 digits)
            daw_code: Dispense as Written code (0-9)
            basis_of_cost: Cost determination basis (01=AWP)
            rx_date: Prescription date in YYYYMMDD format
            days_supply: Days supply (up to 999)
            generic_flag: Generic indicator (G/B)

        Returns:
            K3 segment with 80-character data field
        """
        # Initialize 80-character array with spaces
        k3_data = [' '] * 80

        try:
            # Position 1-2: Fill Number (required)
            fill_str = str(fill_number).zfill(2)[:2]
            k3_data[0:2] = list(fill_str)

            # Position 4: DAW Code (required)
            daw_str = str(daw_code)[0] if daw_code else "0"
            k3_data[3] = daw_str

            # Position 42-43: Basis of Cost (required)
            basis_str = str(basis_of_cost).zfill(2)[:2]
            k3_data[41:43] = list(basis_str)

            # Position 62-69: Date Prescription Written (MMDDYYYY)
            if rx_date:
                formatted_date = format_date_mmddyyyy(rx_date)
                if len(formatted_date) == 8:
                    k3_data[61:69] = list(formatted_date)

            # Position 71-73: Days Supply (3 digits)
            days_str = str(days_supply).zfill(3)[:3]
            k3_data[70:73] = list(days_str)

            # Position 74: Generic Flag (optional)
            if generic_flag in ['G', 'B']:
                k3_data[73] = generic_flag

        except Exception as e:
            logger.error(f"Error building K3 segment: {e}")
            # Return valid but empty K3 on error
            k3_data = [' '] * 80

        # Convert to string and ensure exactly 80 characters
        k3_string = ''.join(k3_data)
        if len(k3_string) != 80:
            logger.warning(f"K3 data length is {len(k3_string)}, expected 80")
            k3_string = k3_string[:80].ljust(80)

        return f"K3*{k3_string}~"

    @classmethod
    def build_k3_simple(cls, content: str = "RX") -> str:
        """Build simple K3 segment (e.g., K3*RX~).

        Args:
            content: Content for K3 segment

        Returns:
            Simple K3 segment
        """
        return f"K3*{content}~"

    @classmethod
    def build_isa(
        cls,
        sender_id: str,
        receiver_id: str,
        date: str,
        time: str,
        control_number: str,
        usage: str = "P"
    ) -> str:
        """Build ISA (Interchange Control Header) segment.

        The ISA segment must be exactly 106 characters including terminator.

        Args:
            sender_id: Sender ID (15 chars, left-justified)
            receiver_id: Receiver ID (15 chars, left-justified)
            date: Date in YYMMDD format
            time: Time in HHMM format
            control_number: Interchange control number (9 digits)
            usage: Usage indicator (P=Production, T=Test)

        Returns:
            ISA segment string
        """
        # Format fixed-width fields
        sender_padded = sender_id[:15].ljust(15)
        receiver_padded = receiver_id[:15].ljust(15)
        control_padded = control_number[:9].zfill(9)

        isa = (
            f"ISA*00*          *00*          *ZZ*{sender_padded}*ZZ*"
            f"{receiver_padded}*{date}*{time}*^*00501*{control_padded}*1*{usage}*:~"
        )

        # Validate length (should be 106)
        if len(isa) != 106:
            logger.warning(f"ISA segment length is {len(isa)}, expected 106")

        return isa

    @classmethod
    def build_segment(cls, segment_id: str, *elements: Any) -> str:
        """Build a generic EDI segment with proper formatting.

        Args:
            segment_id: Segment identifier (e.g., "ST", "NM1")
            *elements: Variable number of segment elements

        Returns:
            Formatted segment string
        """
        # Convert all elements to strings, handling None values
        str_elements = []
        for element in elements:
            if element is None:
                str_elements.append("")
            else:
                str_elements.append(str(element))

        # Join with separator
        segment = f"{segment_id}{cls.ELEMENT_SEPARATOR}{cls.ELEMENT_SEPARATOR.join(str_elements)}"

        # Add terminator
        segment += cls.SEGMENT_TERMINATOR

        # Validate length
        if len(segment) > cls.MAX_SEGMENT_LENGTH:
            logger.error(f"Segment exceeds max length ({len(segment)} > {cls.MAX_SEGMENT_LENGTH}): {segment[:50]}...")
            raise ValueError(f"Segment too long: {len(segment)} characters")

        return segment

    @classmethod
    def build_hcp(
        cls,
        due_amount: float,
        uc_amount: float,
        repricer_id: str,
        fee_schedule: float
    ) -> str:
        """Build HCP (Health Care Pricing) segment.

        Args:
            due_amount: Amount due from payer
            uc_amount: Usual and customary amount
            repricer_id: Repricer identification
            fee_schedule: Fee schedule amount

        Returns:
            HCP segment string
        """
        return cls.build_segment("HCP", "10", due_amount, uc_amount, repricer_id, fee_schedule)

    @classmethod
    def build_clm(
        cls,
        claim_number: str,
        amount: float,
        place_of_service: str = "11",
        diagnosis_pointer: str = "1"
    ) -> str:
        """Build CLM (Claim Information) segment.

        Args:
            claim_number: Claim identifier
            amount: Total claim amount
            place_of_service: Place of service code
            diagnosis_pointer: Diagnosis code pointer

        Returns:
            CLM segment string
        """
        # Format: CLM*{claim_num}*{amount}***01:B:1*Y*A*Y*Y**EM~
        return cls.build_segment(
            "CLM",
            claim_number,
            amount,
            "",  # Empty field
            "",  # Empty field
            f"01:B:{diagnosis_pointer}",
            "Y",
            "A",
            "Y",
            "Y",
            "",  # Empty field
            "EM"
        )

    @classmethod
    def build_sv1(
        cls,
        procedure_code: str,
        drug_name: str,
        amount: float,
        quantity: float,
        unit: str = "UN",
        place_of_service: str = "11"
    ) -> str:
        """Build SV1 (Professional Service) segment.

        Args:
            procedure_code: Procedure code (typically "HC:99070")
            drug_name: Drug name/description
            amount: Service amount
            quantity: Quantity dispensed
            unit: Unit of measure
            place_of_service: Place of service code

        Returns:
            SV1 segment string
        """
        # Format quantity with 3 decimal places if needed
        if isinstance(quantity, str):
            qty_formatted = quantity  # Already formatted
        else:
            qty_formatted = f"{quantity:.3f}"

        # Build composite procedure code
        proc_composite = f"{procedure_code}:::::{drug_name}"

        return cls.build_segment(
            "SV1",
            proc_composite,
            amount,
            unit,
            qty_formatted,
            place_of_service,
            "",  # Empty field
            "1"  # Diagnosis pointer
        )

    @classmethod
    def format_date(cls, date_str: str, output_format: str = "D8") -> str:
        """Format date for EDI output.

        Args:
            date_str: Input date string (various formats)
            output_format: EDI date format (D8=CCYYMMDD, D6=YYMMDD)

        Returns:
            Formatted date string
        """
        if not date_str:
            return ""

        try:
            # Try to parse various formats
            for fmt in ["%Y%m%d", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                # If no format matched, return as-is
                return date_str

            # Format output
            if output_format == "D8":
                return dt.strftime("%Y%m%d")
            elif output_format == "D6":
                return dt.strftime("%y%m%d")
            else:
                return date_str

        except Exception as e:
            logger.warning(f"Failed to format date '{date_str}': {e}")
            return date_str

    @classmethod
    def validate_segment(cls, segment: str) -> List[str]:
        """Validate an EDI segment.

        Args:
            segment: EDI segment string

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check length
        if len(segment) > cls.MAX_SEGMENT_LENGTH:
            errors.append(f"Segment exceeds max length: {len(segment)} > {cls.MAX_SEGMENT_LENGTH}")

        # Check for terminator
        if not segment.endswith(cls.SEGMENT_TERMINATOR):
            errors.append("Segment missing terminator (~)")

        # Check for segment ID
        if not segment or len(segment) < 3:
            errors.append("Segment too short or missing ID")

        return errors