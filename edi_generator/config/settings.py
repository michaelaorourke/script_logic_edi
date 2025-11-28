"""Configuration settings for EDI 837 Generator.

This module handles all configuration for the EDI generation system,
including MongoDB connection, EDI identifiers, and feature flags.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
import json


@dataclass
class BillingProviderConfig:
    """Configuration for billing provider information."""
    name: str = "ScriptLogic WC LLC"
    npi: str = "000000000"  # Match working reference exactly
    tax_id: str = "832588038"
    address: str = "PO Box 801713"
    city: str = "Kansas City"
    state: str = "MO"
    zip_code: str = "641801713"
    phone: str = "8337274785"
    taxonomy_code: str = "333600000X"


@dataclass
class EDIConfig:
    """Configuration for EDI formatting and identifiers."""
    # ISA/IEA Level
    interchange_sender_id: str = "SCRIPTLOGIC"
    interchange_receiver_id: str = "205367462"
    interchange_control_number: str = "000000005"
    usage_indicator: str = "P"  # P=Production, T=Test

    # GS/GE Level
    functional_group_sender: str = "SCRIPTLOGIC"
    functional_group_receiver: str = "205367462"
    group_control_number: str = "4"

    # ST/SE Level
    transaction_control_number: str = "0001"
    implementation_version: str = "005010X222A1"

    # Submitter/Receiver
    submitter_id: str = "900000000"
    submitter_name: str = "SCRIPTLOGIC"
    submitter_contact_name: str = "Billing"
    submitter_contact_email: str = "Sam@scriptlogicwc.com"
    receiver_name: str = "DATA DIMENSIONS"
    receiver_id: str = "205367462"

    # Payer Information
    payer_name: str = "Midwestern Insurance Alliance"
    payer_id: str = "CB691"

    # Pricing
    repricer_id: str = "852631493"
    use_claim_level_hcp: bool = True
    use_line_level_hcp: bool = True


@dataclass
class DatabaseConfig:
    """Configuration for MongoDB database connection."""
    uri: str = "mongodb://localhost:27017/"
    database_name: str = "scriptlogic"

    # Collection names
    claim_collection: str = "claim_detail"  # Using claim_detail as it has claim_number field
    patient_collection: str = "patient"
    client_collection: str = "client"
    npi_collection: str = "npi"

    # Query settings
    batch_size: int = 1000
    timeout_ms: int = 30000


@dataclass
class OutputConfig:
    """Configuration for output file generation."""
    output_dir: str = "837_output"
    file_prefix: str = "837_db_complete"
    use_timestamp: bool = True
    write_newlines: bool = False  # CRITICAL: Must be False for proper EDI format
    create_debug_file: bool = False
    validate_output: bool = True


@dataclass
class QueryConfig:
    """Configuration for claim query parameters."""
    # Default query mode
    query_mode: str = "all"  # all, claim-ids, client-id, date-range, status

    # Query limits
    max_claims: Optional[int] = None
    default_limit: int = 1000

    # Status filters
    valid_statuses: List[str] = None

    def __post_init__(self):
        if self.valid_statuses is None:
            self.valid_statuses = ["B", "NB", "PB", "P", "F", "AR", "IP"]


class Settings:
    """Main settings class that combines all configuration sections."""

    def __init__(self, config_file: Optional[str] = None, env_prefix: str = "EDI_"):
        """Initialize settings from file and environment variables.

        Args:
            config_file: Path to JSON configuration file
            env_prefix: Prefix for environment variables
        """
        self.billing_provider = BillingProviderConfig()
        self.edi = EDIConfig()
        self.database = DatabaseConfig()
        self.output = OutputConfig()
        self.query = QueryConfig()

        # Load from config file if provided
        if config_file and Path(config_file).exists():
            self._load_from_file(config_file)

        # Override with environment variables
        self._load_from_env(env_prefix)

        # Create output directory if needed
        Path(self.output.output_dir).mkdir(parents=True, exist_ok=True)

    def _load_from_file(self, config_file: str):
        """Load settings from JSON configuration file."""
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Update each configuration section
        for section_name, section_config in config.items():
            if hasattr(self, section_name):
                section = getattr(self, section_name)
                for key, value in section_config.items():
                    if hasattr(section, key):
                        setattr(section, key, value)

    def _load_from_env(self, env_prefix: str):
        """Load settings from environment variables."""
        # MongoDB URI
        if mongo_uri := os.getenv(f"{env_prefix}MONGODB_URI"):
            self.database.uri = mongo_uri

        if db_name := os.getenv(f"{env_prefix}DATABASE_NAME"):
            self.database.database_name = db_name

        # Output directory
        if output_dir := os.getenv(f"{env_prefix}OUTPUT_DIR"):
            self.output.output_dir = output_dir

        # EDI identifiers
        if sender_id := os.getenv(f"{env_prefix}SENDER_ID"):
            self.edi.interchange_sender_id = sender_id
            self.edi.functional_group_sender = sender_id

        if receiver_id := os.getenv(f"{env_prefix}RECEIVER_ID"):
            self.edi.interchange_receiver_id = receiver_id
            self.edi.functional_group_receiver = receiver_id

        # Feature flags
        if use_claim_hcp := os.getenv(f"{env_prefix}USE_CLAIM_LEVEL_HCP"):
            self.edi.use_claim_level_hcp = use_claim_hcp.lower() in ('true', '1', 'yes')

        if use_line_hcp := os.getenv(f"{env_prefix}USE_LINE_LEVEL_HCP"):
            self.edi.use_line_level_hcp = use_line_hcp.lower() in ('true', '1', 'yes')

    def to_dict(self) -> dict:
        """Convert settings to dictionary for serialization."""
        return {
            'billing_provider': self.billing_provider.__dict__,
            'edi': self.edi.__dict__,
            'database': self.database.__dict__,
            'output': self.output.__dict__,
            'query': self.query.__dict__
        }

    def save_to_file(self, file_path: str):
        """Save current settings to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


# Global settings instance
settings = Settings()