"""Isolated persistence foundation for the additive NewsStreamAI V2 model."""

from .database import connect, initialize_database, schema_version
from .identifiers import new_id

__all__ = ["connect", "initialize_database", "new_id", "schema_version"]
