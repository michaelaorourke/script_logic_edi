"""Provider model for prescribers and pharmacies.

This module handles provider data including NPIs, names, and addresses
for both prescribers and pharmacy facilities.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging

from .address import Address
from ..data.provider_addresses import get_pharmacy_address, get_prescriber_data

logger = logging.getLogger(__name__)


@dataclass
class Provider:
    """Represents a healthcare provider (prescriber or pharmacy)."""

    npi: str
    provider_type: str  # "prescriber" or "pharmacy"
    first_name: str = ""
    last_name: str = ""
    organization_name: str = ""
    address: Optional[Address] = None
    phone: str = ""
    taxonomy_code: str = ""

    @classmethod
    def from_npi_record(cls, npi_data: Dict[str, Any], provider_type: str) -> "Provider":
        """Create Provider from NPI database record.

        Args:
            npi_data: NPI record from database
            provider_type: "prescriber" or "pharmacy"

        Returns:
            Provider instance
        """
        if not npi_data:
            return cls(npi="", provider_type=provider_type)

        # Parse name fields
        first_name = str(npi_data.get("first_name", "") or "")
        last_name = str(npi_data.get("last_name", "") or "")
        org_name = str(npi_data.get("provider_name", "") or "")

        # Handle "None" string values
        if org_name == "None":
            org_name = ""

        # Create address
        address = Address.from_dict(npi_data)

        return cls(
            npi=str(npi_data.get("npi", "") or ""),
            provider_type=provider_type,
            first_name=first_name,
            last_name=last_name,
            organization_name=org_name,
            address=address,
            phone=cls._format_phone(npi_data.get("contact_number", "")),
            taxonomy_code=str(npi_data.get("taxonomy_code", "") or "")
        )

    @classmethod
    def from_pharmacy_data(cls, pharmacy_data: Dict[str, Any]) -> "Provider":
        """Create Provider from pharmacy data.

        Args:
            pharmacy_data: Pharmacy data from claim

        Returns:
            Provider instance for pharmacy
        """
        if not pharmacy_data:
            return cls(npi="", provider_type="pharmacy")

        npi = str(pharmacy_data.get("npi", "") or "")
        org_name = str(pharmacy_data.get("provider_name", "") or "")
        if org_name == "None" or org_name == "null":
            org_name = ""

        # Try to get hardcoded address first
        hardcoded = get_pharmacy_address(npi)
        if hardcoded.get("address"):
            address = Address(
                street=hardcoded["address"],
                city=hardcoded["city"],
                state=hardcoded["state"],
                zip_code=hardcoded["zip"]
            )
        else:
            address = Address.from_dict(pharmacy_data)

        return cls(
            npi=npi,
            provider_type="pharmacy",
            organization_name=org_name,
            address=address,
            phone=cls._format_phone(pharmacy_data.get("contact_number", ""))
        )

    @classmethod
    def from_prescriber_data(cls, prescriber_data: Dict[str, Any]) -> "Provider":
        """Create Provider from prescriber data.

        Args:
            prescriber_data: Prescriber data from claim

        Returns:
            Provider instance for prescriber
        """
        if not prescriber_data:
            return cls(npi="", provider_type="prescriber")

        npi = str(prescriber_data.get("npi", "") or "")

        # Try to get hardcoded data first
        hardcoded = get_prescriber_data(npi)
        if hardcoded.get("first_name") or hardcoded.get("last_name"):
            first_name = hardcoded["first_name"]
            last_name = hardcoded["last_name"]
            address = Address(
                street=hardcoded["address"],
                city=hardcoded["city"],
                state=hardcoded["state"],
                zip_code=hardcoded["zip"]
            )
        else:
            # Handle name parsing from MongoDB data
            first_name = str(prescriber_data.get("first_name", "") or "")
            last_name = str(prescriber_data.get("last_name", "") or "")

            # If first/last names are None/empty, parse from provider_name
            if (not first_name or first_name == "None") and (not last_name or last_name == "None"):
                provider_name = str(prescriber_data.get("provider_name", "") or "")
                if ", " in provider_name:
                    # Format: "LAST, FIRST"
                    parts = provider_name.split(", ", 1)
                    if len(parts) == 2:
                        last_name = parts[0].strip()
                        first_name = parts[1].strip()
                elif " " in provider_name:
                    # Format: "FIRST LAST"
                    parts = provider_name.rsplit(" ", 1)
                    if len(parts) == 2:
                        first_name = parts[0].strip()
                        last_name = parts[1].strip()
                else:
                    # Single name - put in last name
                    last_name = provider_name

            # Clean up "None" strings
            if first_name == "None":
                first_name = ""
            if last_name == "None":
                last_name = ""

            address = Address.from_dict(prescriber_data)

        return cls(
            npi=npi,
            provider_type="prescriber",
            first_name=first_name,
            last_name=last_name,
            address=address,
            phone=cls._format_phone(prescriber_data.get("contact_number", ""))
        )

    @staticmethod
    def _format_phone(phone: Any) -> str:
        """Format phone number for EDI output.

        Args:
            phone: Phone number in any format

        Returns:
            10-digit phone number or empty string
        """
        if not phone:
            return ""

        # Convert to string and keep only digits
        import re
        phone_digits = re.sub(r'\D', '', str(phone))

        # Must be exactly 10 digits for US phone
        if len(phone_digits) == 10:
            return phone_digits
        elif len(phone_digits) == 11 and phone_digits[0] == '1':
            return phone_digits[1:]  # Remove country code
        else:
            return ""

    def to_nm1_segment(self, qualifier: str) -> str:
        """Generate NM1 (Name) segment for EDI.

        Args:
            qualifier: EDI qualifier code (e.g., "DK" for prescriber, "77" for facility)

        Returns:
            NM1 segment string
        """
        if self.provider_type == "pharmacy" or qualifier == "77":
            # Facility/Organization format
            # NM1*77*2*None*****XX*{npi}~ (Always use "None" for pharmacy name)
            return f"NM1*{qualifier}*2*None*****XX*{self.npi}~"
        else:
            # Individual format (prescriber)
            # NM1*DK*1*{last}*{first}****XX*{npi}~
            return f"NM1*{qualifier}*1*{self.last_name}*{self.first_name}****XX*{self.npi}~"

    def get_edi_segments(self, qualifier: str) -> List[str]:
        """Get all EDI segments for this provider.

        Args:
            qualifier: EDI qualifier code

        Returns:
            List of EDI segments (NM1, N3, N4)
        """
        segments = [self.to_nm1_segment(qualifier)]

        if self.address:
            segments.extend(self.address.get_edi_segments())
        else:
            # Add default address when no address available (required for validation)
            segments.extend([
                "N3*Address Not Available~",
                "N4*Unknown*XX*00000~"
            ])

        return segments

    def validate(self) -> List[str]:
        """Validate provider data.

        Returns:
            List of validation errors
        """
        errors = []

        # NPI validation
        if not self.npi:
            errors.append("NPI is required")
        elif not self.npi.isdigit():
            errors.append(f"NPI must be numeric: {self.npi}")
        elif len(self.npi) != 10 and self.npi != "000000000":
            errors.append(f"NPI must be 10 digits: {self.npi}")

        # Name validation
        if self.provider_type == "prescriber":
            if not self.last_name:
                errors.append("Prescriber last name is required")
        elif self.provider_type == "pharmacy":
            if not self.organization_name:
                logger.warning("Pharmacy has no organization name")

        # Address validation
        if self.address:
            errors.extend(self.address.validate())

        return errors

    def __str__(self) -> str:
        """String representation for debugging."""
        if self.provider_type == "pharmacy":
            return f"Pharmacy: {self.organization_name} (NPI: {self.npi})"
        else:
            return f"Prescriber: {self.last_name}, {self.first_name} (NPI: {self.npi})"