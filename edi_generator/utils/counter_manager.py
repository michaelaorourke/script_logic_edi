"""EDI counter management with file-based persistence.

This module manages EDI control numbers with file-based persistence,
ensuring unique control numbers across EDI file generations.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import logging
import fcntl

logger = logging.getLogger(__name__)


class EDICounterManager:
    """Manages EDI control numbers with persistence."""

    def __init__(self, counter_dir: Optional[str] = None):
        """Initialize counter manager.

        Args:
            counter_dir: Directory for counter files (default: 837_output/.counters)
        """
        if counter_dir:
            self.counter_dir = Path(counter_dir)
        else:
            self.counter_dir = Path("837_output/.counters")

        self.counter_dir.mkdir(parents=True, exist_ok=True)
        self.counter_file = self.counter_dir / "edi_counters.json"
        self.backup_dir = self.counter_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)

        self._ensure_counters_exist()

    def _ensure_counters_exist(self):
        """Initialize counters if file doesn't exist."""
        if not self.counter_file.exists():
            initial_counters = {
                "interchange_control_number": 5,
                "last_updated": datetime.now().isoformat()
            }
            self._save_counters(initial_counters)
            logger.info(f"Initialized counters at {self.counter_file}")

    def _load_counters(self) -> Dict:
        """Load current counter values."""
        try:
            with open(self.counter_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading counters: {e}")
            raise

    def _save_counters(self, counters: Dict):
        """Save counter values with backup."""
        # Create backup before saving
        if self.counter_file.exists():
            backup_file = self.backup_dir / f"counters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_file.write_text(self.counter_file.read_text())

        # Update timestamp
        counters["last_updated"] = datetime.now().isoformat()

        # Save atomically
        temp_file = self.counter_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(counters, f, indent=2)
        temp_file.replace(self.counter_file)

    def get_next_interchange_number(self) -> str:
        """Get next interchange control number (ISA13).

        Returns:
            Zero-padded 9-digit string
        """
        counters = self._load_counters()
        current = counters["interchange_control_number"]
        counters["interchange_control_number"] = current + 1
        self._save_counters(counters)

        formatted = str(current).zfill(9)
        logger.info(f"Allocated interchange control number: {formatted}")

        # Safety check - ensure exactly 9 characters
        assert len(formatted) == 9, f"Interchange control number must be 9 chars, got {len(formatted)}"
        return formatted

    def get_next_group_number(self) -> str:
        """Get group control number (GS06) - static value.

        Returns:
            Always returns '4' for single group per interchange
        """
        return "4"  # Static - single group per interchange

    def get_transaction_number(self) -> str:
        """Get transaction control number (ST02) - resets per file.

        Returns:
            Always returns '0001' for single transaction per file
        """
        return "0001"  # Always 0001 for single transaction per file

    def get_current_values(self) -> Dict:
        """Get current counter values without incrementing.

        Returns:
            Dictionary with current counter values
        """
        return self._load_counters()

    def reset_counters(self, confirm: bool = False):
        """Reset interchange counter to initial value.

        Args:
            confirm: Must be True to actually reset

        Raises:
            ValueError: If confirm is not True
        """
        if not confirm:
            raise ValueError("Must confirm counter reset")

        # Create backup before reset
        if self.counter_file.exists():
            backup_file = self.backup_dir / f"reset_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_file.write_text(self.counter_file.read_text())

        initial_counters = {
            "interchange_control_number": 1,
            "last_updated": datetime.now().isoformat(),
            "reset_at": datetime.now().isoformat()
        }
        self._save_counters(initial_counters)
        logger.warning("Interchange counter has been reset to 1")

    def set_interchange_counter(self, value: int):
        """Set interchange control number to specific value (for testing or recovery).

        Args:
            value: New interchange control number value
        """
        counters = self._load_counters()
        counters["interchange_control_number"] = value
        logger.info(f"Set interchange control number to {value}")
        self._save_counters(counters)