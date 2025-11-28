"""Address model with safe parsing and EDI formatting.

This module provides safe address parsing from various formats
and generates properly formatted EDI segments.
"""

from dataclasses import dataclass
from typing import Optional, List
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class Address:
    """Represents a physical address with EDI formatting capabilities."""

    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""

    @classmethod
    def from_string(cls, address_str: Optional[str]) -> "Address":
        """Parse address from comma-separated string.

        Args:
            address_str: Address string in format "street, city, state zip"

        Returns:
            Address instance with parsed components
        """
        if not address_str:
            return cls()

        # Handle "None" string
        if address_str == "None" or address_str == "null":
            return cls()

        try:
            # Split by comma
            parts = [p.strip() for p in address_str.split(",")]

            street = parts[0] if len(parts) > 0 else ""
            city = parts[1] if len(parts) > 1 else ""

            # Parse state and zip from last part
            state = ""
            zip_code = ""

            if len(parts) > 2:
                last_part = parts[2].strip()
                # Try to extract state and zip
                # Pattern: STATE ZIP or STATE-ZIP
                match = re.match(r"^([A-Z]{2})\s*(\d{5}(?:-?\d{4})?)$", last_part)
                if match:
                    state = match.group(1)
                    zip_code = match.group(2)
                else:
                    # Just use as-is
                    state = last_part

            return cls(
                street=street,
                city=city,
                state=state,
                zip_code=zip_code
            )

        except Exception as e:
            logger.warning(f"Failed to parse address '{address_str}': {e}")
            return cls()

    @classmethod
    def from_dict(cls, data: dict, prefix: str = "") -> "Address":
        """Create Address from dictionary with optional field prefix.

        Args:
            data: Dictionary containing address fields
            prefix: Optional prefix for field names (e.g., 'patient_')

        Returns:
            Address instance
        """
        # Try with prefix first
        street = str(data.get(f"{prefix}address", "") or "")
        city = str(data.get(f"{prefix}city", "") or "")
        state = str(data.get(f"{prefix}state", "") or "")
        zip_code = data.get(f"{prefix}zip", "")

        # For providers, also try provider_ prefix
        if not street and not city:
            street = str(data.get("provider_address", "") or "")
            city = str(data.get("provider_city", "") or "")
            state = str(data.get("provider_state", "") or "")
            zip_code = data.get("provider_zip", "") or zip_code

        # Clean up "None" strings
        if street == "None":
            street = ""
        if city == "None":
            city = ""
        if state == "None":
            state = ""

        return cls(
            street=street,
            city=city,
            state=state,
            zip_code=cls._format_zip(zip_code)
        )

    @staticmethod
    def _format_zip(zip_value: any) -> str:
        """Format ZIP code for EDI output.

        Args:
            zip_value: ZIP code value (string or int)

        Returns:
            Formatted ZIP code string, "00000" if invalid
        """
        if not zip_value:
            return "00000"

        # Convert to string and remove non-digits
        zip_str = re.sub(r'\D', '', str(zip_value))

        if not zip_str:
            return "00000"

        # Pad with zeros if too short
        if len(zip_str) < 5:
            zip_str = zip_str.zfill(5)

        # Truncate if too long
        if len(zip_str) > 9:
            zip_str = zip_str[:9]

        return zip_str

    def to_n3_segment(self) -> str:
        """Generate N3 (Address) segment for EDI.

        Returns:
            N3 segment string (e.g., "N3*123 Main St~")
        """
        # Provide default if street is empty (required for data element 166)
        street_value = self.street if self.street and self.street.strip() else "Address Not Available"
        return f"N3*{street_value}~"

    def to_n4_segment(self) -> str:
        """Generate N4 (City/State/ZIP) segment for EDI.

        Returns:
            N4 segment string (e.g., "N4*Kansas City*MO*64180~")
        """
        # Format ZIP code
        zip_formatted = self._format_zip(self.zip_code)

        # Ensure state is 2 characters
        state_formatted = self.state[:2] if self.state else "XX"

        # Provide default city if empty (required for data element 19)
        city_value = self.city if self.city and self.city.strip() else "Unknown"

        # Ensure ZIP is not empty
        zip_value = zip_formatted if zip_formatted and zip_formatted.strip() else "00000"

        return f"N4*{city_value}*{state_formatted}*{zip_value}~"

    def get_edi_segments(self) -> List[str]:
        """Get both N3 and N4 segments for EDI output.

        Returns:
            List containing N3 and N4 segments
        """
        return [
            self.to_n3_segment(),
            self.to_n4_segment()
        ]

    def is_empty(self) -> bool:
        """Check if address has any data.

        Returns:
            True if all fields are empty
        """
        return not any([self.street, self.city, self.state, self.zip_code])

    def validate(self) -> List[str]:
        """Validate address fields.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # State validation
        if self.state and len(self.state) != 2:
            errors.append(f"State must be 2 characters: {self.state}")

        if self.state and not self.state.isalpha():
            errors.append(f"State must contain only letters: {self.state}")

        # ZIP validation
        if self.zip_code and self.zip_code != "00000":
            zip_clean = re.sub(r'\D', '', self.zip_code)
            if len(zip_clean) not in [5, 9]:
                errors.append(f"ZIP must be 5 or 9 digits: {self.zip_code}")

        return errors

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"