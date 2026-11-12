"""The game's database: SQLite through the standard library.

One connection, guarded by a lock; every write is a short transaction. Migrations are the numbered SQL
files in backend/migrations, applied in order and recorded in schema_migrations. Nothing is ever dropped.

Hosts that wipe their disk on deploy (Render's free tier) keep the database in the same S3-compatible
bucket the game already uses: restored at startup, and a consistent snapshot uploaded shortly after
any change. Single instance only.

    python -m backend.db migrate     # create or migrate the database at DATABASE_PATH
"""

import asyncio
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

log = logging.getLogger("dadi.db")
MIGRATIONS = Path(__file__).parent / "migrations"
SNAPSHOT_KEY = "db/hangup.sqlite"
SNAPSHOT_EVERY = 30  # seconds

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_dirty = False


def path() -> Path:
    return Path(config.DATABASE_PATH)


def connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            path().parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path(), check_same_thread=False, isolation_level=None)  # we BEGIN ourselves
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            _conn = conn
        return _conn


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


@contextmanager
def tx():
    """One transaction. Either everything inside it happens, or none of it does."""
    global _dirty
    with _lock:
        conn = connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        _dirty = True


def rows(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, args).fetchall()


def row(sql: str, args: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        return connect().execute(sql, args).fetchone()


async def run(fn, *args, **kwargs):
    """Database work off the event loop, so a write never holds up a call."""
    return await asyncio.to_thread(fn, *args, **kwargs)


def migrate() -> list[str]:
    """Apply every migration not yet applied, each in its own transaction."""
    applied = []
    with _lock:
        conn = connect()
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for file in sorted(MIGRATIONS.glob("*.sql")):
            if file.stem in done:
                continue
            script = f"BEGIN IMMEDIATE;\n{file.read_text()}\nINSERT INTO schema_migrations VALUES ('{file.stem}', {int(time.time())});\nCOMMIT;"
            try:
                conn.executescript(script)
            except sqlite3.Error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            applied.append(file.stem)
            log.info("Applied migration %s", file.stem)
    return applied


# ---------- durability on hosts without a persistent disk ----------

def _snapshot_bytes() -> bytes:
    fd, tmp = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        with _lock:
            dst = sqlite3.connect(tmp)
            connect().backup(dst)  # a consistent copy, even mid-traffic
            dst.close()
        return Path(tmp).read_bytes()
    finally:
        os.unlink(tmp)


async def restore(store) -> None:
    """Before first use: bring back the last snapshot if this disk is empty."""
    if not config.S3_BUCKET or path().exists():
        return
    try:
        data = await store.get(SNAPSHOT_KEY)
    except Exception as e:
        log.error("Could not restore the database snapshot: %s", e)
        raise
    if data:
        path().parent.mkdir(parents=True, exist_ok=True)
        path().write_bytes(data)
        log.info("Restored the database from the bucket (%d KB)", len(data) // 1024)


async def snapshot(store) -> None:
    global _dirty
    if not config.S3_BUCKET or not _dirty:
        return
    _dirty = False
    try:
        data = await asyncio.to_thread(_snapshot_bytes)
        await store.put(SNAPSHOT_KEY, data, "application/vnd.sqlite3")
    except Exception as e:
        _dirty = True  # try again next time
        log.warning("Could not upload the database snapshot: %s", e)


async def snapshot_forever(store) -> None:
    while True:
        await asyncio.sleep(SNAPSHOT_EVERY)
        await snapshot(store)


if __name__ == "__main__":
    if sys.argv[1:] == ["migrate"]:
        print("applied:", migrate() or "nothing, already up to date", "->", path())
    else:
        print(__doc__)
