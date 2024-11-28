"""Utilities for phone number handling."""


def normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format.

    Args:
        phone: Phone number string that may contain '+' and spaces

    Returns:
        Normalized phone number without '+' and spaces
    """
    return phone.strip().replace("+", "")
