"""The schema carries a version, and each migration runs once, in order.

Without a version, every open re-inspected every table and an upgrade could
not tell a column the user's database never had from one it dropped; nor could
an older Pulse notice it was opening a database a newer one had changed.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from pulse.store.db import (
    MIGRATIONS,
    Migration,
    SchemaTooNewError,
    connect,
    migrate,
    schema_version,
)

LATEST = MIGRATIONS[-1].version


def _raw(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}


def test_a_new_database_starts_at_the_latest_version(tmp_path: Path) -> None:
    """SCHEMA already has every change, so a fresh install replays none of them."""
    connect(tmp_path / "new.db").close()

    with _raw(tmp_path / "new.db") as connection:
        assert schema_version(connection) == LATEST
        assert "carried_seconds" in _columns(connection, "run_steps")


def test_a_database_already_at_version_2_gains_context_tokens(tmp_path: Path) -> None:
    """The column landed in migration 1 after version 2 had shipped, so an
    upgraded database never received the ALTER and every read of run_steps failed.
    """
    path = tmp_path / "v2.db"
    connect(path).close()
    with _raw(path) as connection:
        connection.execute("ALTER TABLE run_steps DROP COLUMN context_tokens")
        connection.execute("PRAGMA user_version = 2")

    connect(path).close()

    with _raw(path) as connection:
        assert schema_version(connection) == LATEST
        assert "context_tokens" in _columns(connection, "run_steps")


def test_a_database_from_before_versioning_gets_the_missing_columns(tmp_path: Path) -> None:
    """Version 0 is every database Pulse wrote before the schema had a version."""
    path = tmp_path / "old.db"
    connect(path).close()
    with _raw(path) as connection:
        connection.execute("ALTER TABLE run_steps DROP COLUMN carried_seconds")
        connection.execute("ALTER TABLE runs DROP COLUMN branch")
        connection.execute("PRAGMA user_version = 0")

    connect(path).close()

    with _raw(path) as connection:
        assert schema_version(connection) == LATEST
        assert "carried_seconds" in _columns(connection, "run_steps")
        assert "branch" in _columns(connection, "runs")


def _unversioned(path: Path) -> None:
    connect(path).close()
    with _raw(path) as connection:
        connection.execute("ALTER TABLE runs DROP COLUMN branch")
        connection.execute("PRAGMA user_version = 0")


def _open_together(path: Path, workers: int) -> list[sqlite3.Error]:
    start = threading.Barrier(workers, timeout=5)
    errors: list[sqlite3.Error] = []

    def open_database() -> None:
        start.wait()
        try:
            connect(path).close()
        except sqlite3.Error as error:
            errors.append(error)

    threads = [threading.Thread(target=open_database) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def test_connections_opened_together_on_an_old_database_migrate_it_once(tmp_path: Path) -> None:
    """The first daemon start after an upgrade serves concurrent requests, and each
    one opens the database: a migration that two of them run at once must not fail
    either request nor apply its change twice.
    """
    for attempt in range(5):
        path = tmp_path / f"old-{attempt}.db"
        _unversioned(path)

        assert _open_together(path, workers=4) == []
        with _raw(path) as connection:
            assert schema_version(connection) == LATEST
            assert "branch" in _columns(connection, "runs")


def test_a_migration_already_applied_is_not_run_again(tmp_path: Path) -> None:
    connection = _raw(tmp_path / "db.sqlite")
    migrate(connection)
    calls: list[int] = []

    def record(_connection: sqlite3.Connection) -> set[tuple[str, str]]:
        calls.append(1)
        return set()

    later = (*MIGRATIONS, Migration(version=LATEST + 1, apply=record))
    migrate(connection, later)
    migrate(connection, later)

    assert calls == [1]
    assert schema_version(connection) == LATEST + 1


def test_a_failed_migration_keeps_the_last_good_version(tmp_path: Path) -> None:
    """A crash halfway must not record a version whose change never landed."""
    connection = _raw(tmp_path / "db.sqlite")
    migrate(connection)

    def adds_then_breaks(conn: sqlite3.Connection) -> set[tuple[str, str]]:
        conn.execute("ALTER TABLE runs ADD COLUMN half_done TEXT")
        conn.execute("SELECT * FROM no_such_table")
        return set()

    with pytest.raises(sqlite3.OperationalError):
        migrate(connection, (*MIGRATIONS, Migration(version=LATEST + 1, apply=adds_then_breaks)))

    assert schema_version(connection) == LATEST
    assert "half_done" not in _columns(connection, "runs")


def test_a_migration_failing_outside_sqlite_releases_the_database(tmp_path: Path) -> None:
    """A bug in `apply` (a `KeyError`) left the write lock held until garbage collection.

    Every other connection, the daemon's included, then failed with `database is locked`.
    """
    path = tmp_path / "db.sqlite"
    connection = _raw(path)
    migrate(connection)

    def adds_then_bugs(conn: sqlite3.Connection) -> set[tuple[str, str]]:
        conn.execute("ALTER TABLE runs ADD COLUMN half_done TEXT")
        raise KeyError("bug in a migration")

    with pytest.raises(KeyError):
        migrate(connection, (*MIGRATIONS, Migration(version=LATEST + 1, apply=adds_then_bugs)))

    assert not connection.in_transaction
    other = sqlite3.connect(str(path), timeout=0)
    other.execute("BEGIN IMMEDIATE")
    other.rollback()
    other.close()
    assert "half_done" not in _columns(connection, "runs")
    assert schema_version(connection) == LATEST


def test_an_older_pulse_refuses_a_database_a_newer_one_migrated(tmp_path: Path) -> None:
    """Writing through a schema it does not know could corrupt the user's runs."""
    path = tmp_path / "future.db"
    connect(path).close()
    with _raw(path) as connection:
        connection.execute(f"PRAGMA user_version = {LATEST + 1}")

    with pytest.raises(SchemaTooNewError, match=f"version {LATEST + 1}"):
        connect(path)


def test_an_older_pulse_leaves_a_newer_database_untouched(tmp_path: Path) -> None:
    """Refusing after writing is too late: a table the newer schema dropped comes back."""
    path = tmp_path / "future.db"
    connect(path).close()
    with _raw(path) as connection:
        connection.execute("DROP TABLE run_events")
        connection.execute(f"PRAGMA user_version = {LATEST + 1}")

    with pytest.raises(SchemaTooNewError):
        connect(path)

    with _raw(path) as connection:
        tables = {str(row["name"]) for row in connection.execute("SELECT name FROM sqlite_master")}
        assert "run_events" not in tables


def test_versions_are_strictly_increasing() -> None:
    versions = [migration.version for migration in MIGRATIONS]

    assert versions == sorted(set(versions))
    assert versions[0] == 1
