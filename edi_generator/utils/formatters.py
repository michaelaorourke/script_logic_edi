"""Utility functions for EDI field formatting."""

from datetime import datetime
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)


def format_date_yyyymmdd(date_value: Union[str, datetime, None]) -> str:
    """Format date to YYYYMMDD format for EDI.

    Args:
        date_value: Date in various formats:
            - datetime object
            - "YYYY-MM-DD HH:MM:SS" string
            - "YYYY-MM-DD" string
            - "YYYYMMDD" string
            - None

    Returns:
        Date string in YYYYMMDD format, or empty string if invalid
    """
    if not date_value:
        return ""

    try:
        # Handle datetime objects
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y%m%d')

        # Convert to string
        date_str = str(date_value)

        # Remove time portion if present
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]

        # Handle different string formats
        if '-' in date_str:
            # YYYY-MM-DD format
            parts = date_str.split('-')
            if len(parts) == 3:
                return ''.join(parts)
        elif len(date_str) == 8 and date_str.isdigit():
            # Already in YYYYMMDD format
            return date_str
        else:
            logger.warning(f"Unknown date format: {date_value}")
            return ""

    except Exception as e:
        logger.error(f"Error formatting date {date_value}: {e}")
        return ""


def format_date_yymmdd(date_value: Union[str, datetime, None]) -> str:
    """Format date to YYMMDD format for ISA segment.

    Args:
        date_value: Date value in various formats

    Returns:
        Date string in YYMMDD format
    """
    yyyymmdd = format_date_yyyymmdd(date_value)
    if len(yyyymmdd) == 8:
        return yyyymmdd[2:]  # Remove century
    return ""


def format_date_mmddyyyy(date_value: Union[str, datetime, None]) -> str:
    """Format date to MMDDYYYY format for NCPDP K3 segment.

    Args:
        date_value: Date value in various formats

    Returns:
        Date string in MMDDYYYY format
    """
    yyyymmdd = format_date_yyyymmdd(date_value)
    if len(yyyymmdd) == 8:
        return yyyymmdd[4:6] + yyyymmdd[6:8] + yyyymmdd[0:4]
    return ""


def format_amount(amount: Union[float, int, str, None]) -> str:
    """Format monetary amount to 2 decimal places.

    Args:
        amount: Monetary amount

    Returns:
        Amount string with 2 decimal places
    """
    if amount is None:
        return "0.00"

    try:
        # Convert to float
        amount_float = float(amount)
        return f"{amount_float:.2f}"
    except (ValueError, TypeError):
        logger.warning(f"Invalid amount value: {amount}")
        return "0.00"


def format_quantity(quantity: Union[float, int, str, None]) -> str:
    """Format quantity to 3 decimal places.

    Args:
        quantity: Quantity value

    Returns:
        Quantity string with 3 decimal places
    """
    if quantity is None:
        return "0.000"

    try:
        qty_float = float(quantity)
        return f"{qty_float:.3f}"
    except (ValueError, TypeError):
        logger.warning(f"Invalid quantity value: {quantity}")
        return "0.000"


def format_phone(phone: Union[str, None]) -> str:
    """Format phone number to 10 digits only.

    Args:
        phone: Phone number with possible formatting

    Returns:
        10-digit phone number string
    """
    if not phone:
        return ""

    # Remove all non-digit characters
    phone_digits = ''.join(filter(str.isdigit, str(phone)))

    # Ensure 10 digits
    if len(phone_digits) == 10:
        return phone_digits
    elif len(phone_digits) == 11 and phone_digits[0] == '1':
        return phone_digits[1:]  # Remove country code
    else:
        logger.warning(f"Invalid phone number length: {phone}")
        return phone_digits[:10].ljust(10, '0')


def format_zip(zip_code: Union[str, int, None]) -> str:
    """Format ZIP code to 5 or 9 digits.

    Args:
        zip_code: ZIP code value

    Returns:
        5 or 9 digit ZIP code string
    """
    if not zip_code:
        return ""

    # Convert to string and remove non-digits
    zip_str = ''.join(filter(str.isdigit, str(zip_code)))

    # Return 5 or 9 digits
    if len(zip_str) >= 9:
        return zip_str[:9]
    elif len(zip_str) >= 5:
        return zip_str[:5]
    else:
        return zip_str.ljust(5, '0')


def truncate_element(value: str, max_length: int) -> str:
    """Truncate element to maximum allowed length.

    Args:
        value: Element value
        max_length: Maximum allowed length

    Returns:
        Truncated string
    """
    if not value:
        return ""

    value_str = str(value)
    if len(value_str) > max_length:
        logger.warning(f"Truncating element from {len(value_str)} to {max_length} chars")
        return value_str[:max_length]

    return value_str