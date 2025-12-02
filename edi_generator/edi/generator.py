"""EDI 837 file generator with proper segment ordering and formatting.

This module generates complete EDI 837 Professional claim files
maintaining exact compliance with X12 specifications.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from ..config.settings import Settings, EDIConfig, BillingProviderConfig
from ..models.address import Address
from ..models.provider import Provider
from .segment_builder import EDISegmentBuilder
from ..utils.formatters import (
    format_date_yyyymmdd,
    format_date_yymmdd,
    format_amount,
    format_quantity,
    format_phone,
    truncate_element
)
from ..utils.counter_manager import EDICounterManager

logger = logging.getLogger(__name__)


class EDIGenerator:
    """Generates EDI 837 Professional claim files from MongoDB data."""

    def __init__(self, settings: Settings):
        """Initialize EDI generator.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.edi_config = settings.edi
        self.billing_provider = settings.billing_provider
        self.segment_builder = EDISegmentBuilder()
        self.counter_manager = EDICounterManager()

        # Counters for hierarchical levels and service lines
        self.hl_counter = 0
        self.lx_counter = 0
        self.st_index = 0

    def generate_from_claims(self, claims: List[Dict[str, Any]]) -> List[str]:
        """Generate complete EDI file from claim data.

        Args:
            claims: List of claim records with embedded related data

        Returns:
            List of EDI segments
        """
        segments = []

        # Generate timestamps
        now = datetime.now()
        isa_date = now.strftime("%y%m%d")
        isa_time = now.strftime("%H%M")
        bht_date = now.strftime("%Y%m%d")
        bht_time = now.strftime("%H%M")

        # Get next control numbers from counter manager
        interchange_num = self.counter_manager.get_next_interchange_number()
        group_num = self.counter_manager.get_next_group_number()
        trans_num = self.counter_manager.get_transaction_number()

        # ISA - Interchange Control Header
        segments.append(self.segment_builder.build_isa(
            sender_id=self.edi_config.interchange_sender_id,
            receiver_id=self.edi_config.interchange_receiver_id,
            date=isa_date,
            time=isa_time,
            control_number=interchange_num,  # Dynamic control number
            usage=self.edi_config.usage_indicator
        ))

        # GS - Functional Group Header
        segments.append(self.segment_builder.build_segment(
            "GS", "HC",
            self.edi_config.functional_group_sender,
            self.edi_config.functional_group_receiver,
            bht_date,
            isa_time,
            group_num,  # Dynamic control number
            "X",
            self.edi_config.implementation_version
        ))

        # ST - Transaction Set Header
        self.st_index = len(segments)
        segments.append(self.segment_builder.build_segment(
            "ST", "837",
            trans_num,  # Dynamic control number (always "0001")
            self.edi_config.implementation_version
        ))

        # BHT - Beginning of Hierarchical Transaction
        segments.append(self.segment_builder.build_segment(
            "BHT", "0019", "00",
            f"SCRIPTLOGIC_{bht_date}",
            bht_date,
            bht_time,
            "CH"
        ))

        # 1000A - Submitter
        segments.append(self.segment_builder.build_segment(
            "NM1", "41", "2",
            self.edi_config.submitter_name,
            "", "", "", "",
            "46",
            self.edi_config.submitter_id
        ))

        segments.append(self.segment_builder.build_segment(
            "PER", "IC",
            self.edi_config.submitter_contact_name,
            "EM",
            self.edi_config.submitter_contact_email
        ))

        # 1000B - Receiver
        segments.append(self.segment_builder.build_segment(
            "NM1", "40", "2",
            self.edi_config.receiver_name,
            "", "", "", "",
            "46",
            self.edi_config.receiver_id
        ))

        # 2000A - Billing Provider Hierarchical Level
        self.hl_counter = 1
        segments.append(self.segment_builder.build_segment(
            "HL", self.hl_counter, "", "20", "1"
        ))

        # 2010AA - Billing Provider
        segments.append(self.segment_builder.build_segment(
            "PRV", "BI", "PXC",
            self.billing_provider.taxonomy_code
        ))

        segments.append(self.segment_builder.build_segment(
            "NM1", "85", "2",
            self.billing_provider.name,
            "", "", "", "",
            "XX",
            self.billing_provider.npi
        ))

        billing_address = Address(
            street=self.billing_provider.address,
            city=self.billing_provider.city,
            state=self.billing_provider.state,
            zip_code=self.billing_provider.zip_code
        )
        segments.extend(billing_address.get_edi_segments())

        segments.append(self.segment_builder.build_segment(
            "REF", "EI",
            self.billing_provider.tax_id
        ))

        segments.append(self.segment_builder.build_segment(
            "PER", "IC",
            self.billing_provider.name,
            "TE",
            self.billing_provider.phone
        ))

        # Group claims by patient
        patients_dict = self._group_claims_by_patient(claims)

        # Process each patient
        for claim_num, patient_data in patients_dict.items():
            segments.extend(self._generate_patient_segments(patient_data, claim_num))

        # SE - Transaction Set Trailer
        segment_count = len(segments) - self.st_index + 1
        segments.append(self.segment_builder.build_segment(
            "SE", segment_count,
            trans_num  # Must match ST02
        ))

        # GE - Functional Group Trailer
        segments.append(self.segment_builder.build_segment(
            "GE", "1",
            group_num  # Must match GS06
        ))

        # IEA - Interchange Control Trailer
        segments.append(self.segment_builder.build_segment(
            "IEA", "1",
            interchange_num  # Must match ISA13
        ))

        logger.info(f"Generated {len(segments)} EDI segments")
        return segments

    def _group_claims_by_patient(self, claims: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """Group claims by patient for hierarchical structure.

        Args:
            claims: List of claim records

        Returns:
            Dictionary keyed by claim_number with patient data
        """
        patients_dict = {}

        for claim in claims:
            # claim_detail has claim_number directly
            claim_number = claim.get("claim_number", "")
            if not claim_number:
                # Fallback to subscriber_num for claim collection
                claim_number = claim.get("subscriber_num", "")
            if not claim_number:
                continue

            if claim_number not in patients_dict:
                # Get patient data from embedded lookup
                patient_info = claim.get("patient_data", {})
                client_info = claim.get("client_data", {})

                patients_dict[claim_number] = {
                    "patient": patient_info,
                    "client": client_info,
                    "prescriptions": []
                }

            # Add prescription data
            patients_dict[claim_number]["prescriptions"].append(claim)

        return patients_dict

    def _generate_patient_segments(self, patient_data: Dict, claim_number: str = "") -> List[str]:
        """Generate all segments for a patient and their prescriptions.

        Args:
            patient_data: Patient data with prescriptions

        Returns:
            List of EDI segments
        """
        segments = []
        patient = patient_data.get("patient", {})
        client = patient_data.get("client", {})
        prescriptions = patient_data.get("prescriptions", [])

        if not prescriptions:
            return segments

        # 2000B - Subscriber Hierarchical Level
        self.hl_counter += 1
        subscriber_hl = self.hl_counter
        segments.append(self.segment_builder.build_segment(
            "HL", subscriber_hl, "1", "22", "1"
        ))

        # 2010BA - Subscriber
        segments.append(self.segment_builder.build_segment(
            "SBR", "P", "", "", "", "", "", "", "", "WC"
        ))

        segments.append(self.segment_builder.build_segment(
            "NM1", "IL", "2",
            client.get("name", self.edi_config.payer_name)
        ))

        # 2010BB - Payer
        segments.append(self.segment_builder.build_segment(
            "NM1", "PR", "2",
            client.get("name", self.edi_config.payer_name),
            "", "", "", "",
            "PI",
            self.edi_config.payer_id
        ))

        # Payer address
        payer_address = Address.from_dict(client)
        if not payer_address.is_empty():
            segments.extend(payer_address.get_edi_segments())
        else:
            # Use default if no address
            segments.extend([
                "N3*PO BOX 436909~",
                "N4*Louisville*KY*40253~"
            ])

        # 2000C - Patient Hierarchical Level
        self.hl_counter += 1
        segments.append(self.segment_builder.build_segment(
            "HL", self.hl_counter, subscriber_hl, "23", "0"
        ))

        # 2010CA - Patient
        segments.append(self.segment_builder.build_segment("PAT", "20"))

        segments.append(self.segment_builder.build_segment(
            "NM1", "QC", "1",
            patient.get("last_name", ""),
            patient.get("first_name", "")
        ))

        # Patient address
        patient_address = Address.from_dict(patient)
        segments.extend(patient_address.get_edi_segments())

        # Patient demographics - format date properly
        date_of_injury = format_date_yyyymmdd(patient.get("date_of_injury", ""))

        segments.append(self.segment_builder.build_segment(
            "DMG", "D8",
            date_of_injury,
            patient.get("gender", "")
        ))

        segments.append(self.segment_builder.build_segment(
            "REF", "Y4",
            patient.get("claim_number", claim_number)  # Use passed claim_number if patient doesn't have it
        ))

        segments.append(self.segment_builder.build_segment(
            "REF", "SY", "999999999"
        ))

        # Process each prescription as a claim
        self.lx_counter = 1
        for prescription in prescriptions:
            segments.extend(self._generate_prescription_segments(prescription, patient, claim_number))

        return segments

    def _generate_prescription_segments(self, prescription: Dict, patient: Dict, claim_number: str = "") -> List[str]:
        """Generate segments for a single prescription/claim.

        Args:
            prescription: Prescription/claim data
            patient: Patient data

        Returns:
            List of EDI segments
        """
        segments = []

        # Get embedded NPI data
        pharmacy_data = prescription.get("pharmacy_npi_data", {})
        prescriber_data = prescription.get("prescriber_npi_data", {})

        # Create provider objects with fallback to embedded data
        if not pharmacy_data:
            # Use embedded pharmacy data from claim
            pharmacy = Provider(
                npi=prescription.get("pharmacy_npi", ""),
                organization_name=prescription.get("pharmacy", ""),
                provider_type="pharmacy"
            )
        else:
            pharmacy = Provider.from_pharmacy_data(pharmacy_data)

        if not prescriber_data:
            # Use embedded prescriber data from claim
            prescriber_name = prescription.get("prescriber_name", "")
            first_name = ""
            last_name = prescriber_name  # Default to full name as last name

            # Try to parse name if it contains comma
            if ", " in prescriber_name:
                parts = prescriber_name.split(", ", 1)
                if len(parts) == 2:
                    last_name = parts[0].strip()
                    first_name = parts[1].strip()

            prescriber = Provider(
                npi=prescription.get("doctor_no", ""),
                first_name=first_name,
                last_name=last_name,
                provider_type="prescriber"
            )
        else:
            prescriber = Provider.from_prescriber_data(prescriber_data)

        # 2300 - Claim Information
        segments.append(self._generate_clm_segment(prescription, patient, claim_number))

        segments.append(self.segment_builder.build_segment(
            "DTP", "439", "D8",
            format_date_yyyymmdd(patient.get("date_of_injury", ""))
        ))

        # REF*D9 - Claim reference
        trans_date = format_date_yyyymmdd(prescription.get('trans_date', ''))
        unique_id = str(prescription.get('_id', {}).get('$oid', '') if isinstance(prescription.get('_id'), dict) else prescription.get('_id', ''))
        ref_d9 = truncate_element(
            f"{trans_date}"
            f"{pharmacy.npi}"
            f"{unique_id}",
            50  # REF02 max length is 50 characters
        )
        segments.append(self.segment_builder.build_segment(
            "REF", "D9", ref_d9
        ))

        # K3*RX - Simple K3 segment
        segments.append("K3*RX~")

        # HI - Diagnosis
        segments.append(self.segment_builder.build_segment(
            "HI", "ABK:R52"
        ))

        # HCP - Claim level pricing (optional)
        if self.edi_config.use_claim_level_hcp:
            # Calculate fee_schedule if not present
            fee_schedule = prescription.get("fee_schedule") or prescription.get("plan_paid", 0)
            due_amount = prescription.get("due_amount") or prescription.get("member_paid", 0)

            segments.append(self.segment_builder.build_hcp(
                due_amount=format_amount(due_amount),
                uc_amount=format_amount(prescription.get("u_and_c", 0)),
                repricer_id=self.edi_config.repricer_id,
                fee_schedule=format_amount(fee_schedule)
            ))

        # 2310C - Service Facility (Pharmacy)
        segments.extend(pharmacy.get_edi_segments("77"))

        # 2400 - Service Line
        segments.extend(self._generate_service_line_segments(prescription, prescriber))

        return segments

    def _generate_clm_segment(self, prescription: Dict, patient: Dict, claim_number: str = "") -> str:
        """Generate CLM segment for prescription.

        Args:
            prescription: Prescription data
            patient: Patient data

        Returns:
            CLM segment string
        """
        # Calculate amount from available fields
        fee_schedule = prescription.get("fee_schedule") or prescription.get("plan_paid", 0)
        amount = format_amount(fee_schedule)
        return self.segment_builder.build_clm(
            claim_number=patient.get("claim_number", claim_number),  # Use passed claim_number if patient doesn't have it
            amount=amount
        )

    def _generate_service_line_segments(self, prescription: Dict, prescriber: Provider) -> List[str]:
        """Generate 2400 service line segments.

        Args:
            prescription: Prescription data
            prescriber: Prescriber provider object

        Returns:
            List of service line segments
        """
        segments = []

        # LX - Service line counter
        segments.append(self.segment_builder.build_segment(
            "LX", self.lx_counter
        ))

        # SV1 - Professional service
        fee_schedule = prescription.get("fee_schedule") or prescription.get("plan_paid", 0)
        drug_name = prescription.get("drug_name") or prescription.get("drug", "")

        segments.append(self.segment_builder.build_sv1(
            procedure_code="HC:99070",
            drug_name=drug_name,
            amount=format_amount(fee_schedule),
            quantity=format_quantity(prescription.get("quantity", 0))
        ))

        # DTP - Service date
        segments.append(self.segment_builder.build_segment(
            "DTP", "472", "D8",
            format_date_yyyymmdd(prescription.get("trans_date", ""))
        ))

        # REF*6R - Line item control number
        segments.append(self.segment_builder.build_segment(
            "REF", "6R",
            prescription.get("rx_no", "")
        ))

        # K3 - NCPDP segment (80 characters)
        segments.append(self.segment_builder.build_k3_ncpdp(
            fill_number="00",
            daw_code=prescription.get("daw", "0"),
            basis_of_cost="01",
            rx_date=format_date_yyyymmdd(prescription.get("rx_date", "")),
            days_supply=prescription.get("days_supply", 0),
            generic_flag=prescription.get("brand_gen", "")
        ))

        # HCP - Line level pricing (optional)
        if self.edi_config.use_line_level_hcp:
            fee_schedule = prescription.get("fee_schedule") or prescription.get("plan_paid", 0)
            due_amount = prescription.get("due_amount") or prescription.get("member_paid", 0)

            segments.append(self.segment_builder.build_hcp(
                due_amount=format_amount(due_amount),
                uc_amount=format_amount(prescription.get("u_and_c", 0)),
                repricer_id=self.edi_config.repricer_id,
                fee_schedule=format_amount(fee_schedule)
            ))

        # LIN - Drug identification
        segments.append(self.segment_builder.build_segment(
            "LIN", "", "N4",
            prescription.get("ndc", "")
        ))

        # CTP - Drug quantity
        days_supply = format_quantity(prescription.get("days_supply", 0))
        segments.append(self.segment_builder.build_segment(
            "CTP", "", "", "",
            days_supply,
            "ME"
        ))

        # 2310B - Prescriber
        segments.extend(prescriber.get_edi_segments("DK"))

        self.lx_counter += 1
        return segments

    def validate_output(self, segments: List[str]) -> List[str]:
        """Validate EDI output for compliance.

        Args:
            segments: List of EDI segments

        Returns:
            List of validation errors
        """
        errors = []

        # Check ISA segment length
        if segments and len(segments[0]) != 106:
            errors.append(f"ISA segment length is {len(segments[0])}, expected 106")

        # Validate each segment
        for i, segment in enumerate(segments):
            segment_errors = self.segment_builder.validate_segment(segment)
            for error in segment_errors:
                errors.append(f"Segment {i}: {error}")

        # Check for required segments
        required_segments = ["ISA", "GS", "ST", "BHT", "SE", "GE", "IEA"]
        segment_ids = [s[:3] for s in segments if len(s) >= 3]
        for req in required_segments:
            if req not in segment_ids:
                errors.append(f"Missing required segment: {req}")

        # Validate K3 segments
        k3_segments = [s for s in segments if s.startswith("K3*")]
        for k3 in k3_segments:
            if "K3*RX~" not in k3:  # Simple K3
                # Should be NCPDP format - check 80 character data field
                data_part = k3[3:-1]  # Remove K3* and ~
                if len(data_part) != 80:
                    errors.append(f"K3 NCPDP data length is {len(data_part)}, expected 80")

        return errors