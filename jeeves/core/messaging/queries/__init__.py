"""Database queries package."""

from .dialog import DialogQueries
from .message import MessageQueries

__all__ = [
    "MessageQueries",
    "DialogQueries",
]
