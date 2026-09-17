"""Small SQLite/WAL persistence foundation used by V2 only."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Iterator

from .config import database_path


BUSY_TIMEOUT_MS = 15_000
_SAVEPOINT_SEQUENCE = count()


class V2Connection(sqlite3.Connection):
    """Connection whose context manager closes the local SQLite handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


def _migration_sql(filename: str) -> str:
    return (Path(__file__).parent / "migrations" / filename).read_text(encoding="utf-8")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "provenance_foundations", _migration_sql("0001_provenance.sql")),
    Migration(2, "content_foundations", _migration_sql("0002_content_foundations.sql")),
    Migration(3, "event_foundations", _migration_sql("0003_event_foundations.sql")),
    Migration(4, "truth_and_entities", _migration_sql("0004_truth_entities.sql")),
    Migration(5, "generated_and_summaries", _migration_sql("0005_generated_summaries.sql")),
    Migration(6, "personalization_foundations", _migration_sql("0006_personalization.sql")),
    Migration(7, "derived_search_and_embeddings", _migration_sql("0007_derived_search_embeddings.sql")),
    Migration(8, "shadow_transition_foundations", _migration_sql("0008_shadow_transition.sql")),
    Migration(9, "bookmark_actions", _migration_sql("0009_bookmark_actions.sql")),
    Migration(10, "reaction_actions", _migration_sql("0010_reaction_actions.sql")),
    Migration(11, "event_detail_summaries", _migration_sql("0011_event_detail_summaries.sql")),
    Migration(12, "feed_editorial", _migration_sql("0012_feed_editorial.sql")),
    Migration(13, "editorial_and_provenance", _migration_sql("0013_editorial_and_provenance.sql")),
    Migration(14, "editorial_publication_pipeline", _migration_sql("0014_editorial_publication_pipeline.sql")),
)


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a V2 SQLite connection with the mandatory local safety settings."""
    resolved_path = Path(path) if path is not None else database_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved_path, timeout=BUSY_TIMEOUT_MS / 1_000, factory=V2Connection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA wal_autocheckpoint = 1000")
    return connection


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )


def schema_version(connection: sqlite3.Connection) -> int:
    """Return the installed V2 schema version, or zero for a new database."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if exists is None:
        return 0
    row = connection.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
    return int(row["version"])


def initialize_database(path: Path | str | None = None, force: bool = False) -> int:
    """Create or upgrade the isolated V2 database idempotently."""
    connection = connect(path)
    try:
        _ensure_migration_table(connection)
        installed = schema_version(connection)
        latest = MIGRATIONS[-1].version if MIGRATIONS else 0
        if installed > latest:
            raise RuntimeError(f"Database schema version {installed} is newer than this application ({latest})")
        if installed == latest and not force:
            return installed

        for migration in MIGRATIONS:
            if migration.version <= installed:
                continue
            # executescript needs its own explicit transaction; each migration is
            # therefore atomic and its version is only recorded on success.
            name_literal = migration.name.replace("'", "''")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{migration.sql}\n"
                f"INSERT INTO schema_migrations (version, name) VALUES ({migration.version}, '{name_literal}');\n"
                "COMMIT;"
            )
            installed = migration.version
        if installed >= 6:
            try:
                connection.execute("CREATE INDEX IF NOT EXISTS ix_user_scores_ranking ON user_scores(user_id, status, final_score DESC)")
                connection.execute("CREATE INDEX IF NOT EXISTS ix_feed_eligibilities_filter ON feed_eligibilities(user_id, is_current, state, user_score_id)")
            except Exception:
                pass
        if installed >= 13:
            for table, col, col_type in [
                ("events", "event_started_at", "TEXT"),
                ("events", "last_source_update_at", "TEXT"),
                ("events", "independent_sources_count", "INTEGER NOT NULL DEFAULT 1"),
                ("contents", "is_syndicated", "INTEGER NOT NULL DEFAULT 0"),
                ("contents", "syndication_parent_content_id", "TEXT REFERENCES contents(id)"),
            ]:
                try:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
        return installed
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Reserve a short write transaction for future V2 persistence operations."""
    if connection.in_transaction:
        savepoint = f"v2_write_{next(_SAVEPOINT_SEQUENCE)}"
        connection.execute(f"SAVEPOINT {savepoint}")
        try:
            yield connection
        except Exception:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        else:
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
