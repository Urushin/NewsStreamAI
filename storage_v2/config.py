"""Single configuration point for the local V2 SQLite database."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "newsstream_v2.db"


def database_path() -> Path:
    """Return the only configured V2 database path.

    The environment override is intentionally limited to the V2 database so it
    cannot affect the legacy JSON files or the legacy vector database.
    """
    configured = os.getenv("NEWSSTREAM_V2_DB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DATABASE_PATH


def shadow_mode_enabled() -> bool:
    """Whether the legacy daemon may perform additive V2 shadow writes."""
    return os.getenv("NEWSSTREAM_V2_SHADOW_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def v2_read_enabled() -> bool:
    return read_mode() == "v2"


def read_mode() -> str:
    """One reversible user-read switch; V2 is the normal path."""
    return "v1" if os.getenv("NEWSSTREAM_READ_MODE", "v2").strip().lower() == "v1" else "v2"


def v2_canonical_write_enabled() -> bool:
    """Canonical persistence is on by default; set false only for emergency rollback."""
    return os.getenv("NEWSSTREAM_V2_CANONICAL_WRITE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def v2_delivery_enabled() -> bool:
    return os.getenv("NEWSSTREAM_V2_DELIVERY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
