"""Enums for messaging."""

from enum import Enum


class MessageDirection(str, Enum):
    """Message direction."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class DialogStatus(str, Enum):
    """Dialog status."""

    # Active state
    active = "active"  # Dialog is in progress

    # Final states
    success = "success"  # Successful outcome (meeting/info/etc)
    rejected = "rejected"  # Explicit rejection
    not_qualified = "not_qualified"  # Contact doesn't match criteria
    blocked = "blocked"  # Account/dialog got blocked
    expired = "expired"  # Dialog considered dead/no response
    stopped = "stopped"  # Manually stopped
