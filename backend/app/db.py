import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db(path: Path) -> None:
    """Create the database from scratch, discarding any previous file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()
