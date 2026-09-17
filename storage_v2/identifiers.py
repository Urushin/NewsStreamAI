"""Internal identifier conventions for V2 persistence."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Create a time-sortable internal identifier.

    Python 3.14 provides UUIDv7.  The fallback keeps this module as the single
    replacement point if an older supported Python runtime is ever required.
    """
    uuid7 = getattr(uuid, "uuid7", None)
    return str(uuid7() if uuid7 is not None else uuid.uuid4())
