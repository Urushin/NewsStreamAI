"""Parse source dates robustly without substituting the ingestion time."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import dateutil.parser


def publication_date(value):
    if not value or not str(value).strip():
        return None
    val = str(value).strip()
    date = None
    try:
        date = datetime.fromisoformat(val.replace('Z', '+00:00'))
    except ValueError:
        try:
            date = parsedate_to_datetime(val)
        except (ValueError, TypeError, OverflowError):
            try:
                date = dateutil.parser.parse(val)
            except Exception:
                return None
    if date is None:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    else:
        date = date.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    # Allow up to 2 hours of server clock skew or future embargo, clamp to now
    if date > now:
        if date <= now + timedelta(hours=2):
            return now
        return None
    return date
