"""SQLite persistence for scan history. All queries are parameterised."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "instance", "kisanlens.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    crop TEXT NOT NULL,
    predicted_class TEXT NOT NULL,
    confidence REAL NOT NULL,
    image_ref TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_session ON scans(session_id, created_at DESC);
"""


@contextmanager
def connect(db_path=None):
    path = db_path or DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def add_scan(session_id, crop, predicted_class, confidence, image_ref, db_path=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO scans (session_id, created_at, crop, predicted_class, confidence, image_ref) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, now, crop, predicted_class, float(confidence), image_ref),
        )
        return cur.lastrowid


def get_scans(session_id, db_path=None):
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, crop, predicted_class, confidence, image_ref "
            "FROM scans WHERE session_id = ? ORDER BY created_at DESC, id DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_scan(scan_id, session_id, db_path=None):
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, created_at, crop, predicted_class, confidence, image_ref "
            "FROM scans WHERE id = ? AND session_id = ?",
            (scan_id, session_id),
        ).fetchone()
    return dict(row) if row else None


def delete_scan(scan_id, session_id, db_path=None):
    """Delete one scan owned by the session. Returns the image_ref or None."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT image_ref FROM scans WHERE id = ? AND session_id = ?",
            (scan_id, session_id),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM scans WHERE id = ? AND session_id = ?", (scan_id, session_id))
        return row["image_ref"]


def delete_all_scans(session_id, db_path=None):
    """Delete all scans for a session. Returns list of image_refs removed."""
    with connect(db_path) as conn:
        rows = conn.execute("SELECT image_ref FROM scans WHERE session_id = ?", (session_id,)).fetchall()
        conn.execute("DELETE FROM scans WHERE session_id = ?", (session_id,))
    return [r["image_ref"] for r in rows]


def ref_owned(image_ref, session_id, db_path=None):
    """True if the image_ref belongs to a saved scan of this session."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM scans WHERE image_ref = ? AND session_id = ?",
            (image_ref, session_id),
        ).fetchone()
    return row is not None


def all_image_refs(db_path=None):
    with connect(db_path) as conn:
        return {r["image_ref"] for r in conn.execute("SELECT image_ref FROM scans").fetchall()}
