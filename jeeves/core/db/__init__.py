"""Database module."""

from .base import BaseQueries, async_session, engine, get_db
from .decorators import handle_sql_error, with_queries
from .models import Base, utcnow
from .tables import setup_relationships

# Set up model relationships
setup_relationships()

__all__ = [
    "Base",
    "BaseQueries",
    "with_queries",
    "handle_sql_error",
    "engine",
    "async_session",
    "get_db",
    "utcnow",
]
