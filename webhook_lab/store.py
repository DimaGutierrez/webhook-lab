import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(UTC).isoformat()


class CapacityError(Exception):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS inbox (
                    id INTEGER PRIMARY KEY CHECK (id = 1), token TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, received_at TEXT NOT NULL,
                    headers TEXT NOT NULL, body BLOB NOT NULL, size INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    target TEXT NOT NULL, started_at TEXT NOT NULL,
                    duration_ms INTEGER, status TEXT NOT NULL,
                    status_code INTEGER, error TEXT
                );
                CREATE INDEX IF NOT EXISTS attempts_event ON attempts(event_id, started_at);
                CREATE INDEX IF NOT EXISTS events_received ON events(received_at);
            """)
            conn.execute("INSERT OR IGNORE INTO inbox VALUES (1, ?)", (secrets.token_urlsafe(24),))
            conn.execute(
                "UPDATE attempts SET status='interrupted',"
                " error='Process stopped before completion'"
                " WHERE status='pending'"
            )

    def inbox_token(self):
        with self.connect() as conn:
            return conn.execute("SELECT token FROM inbox WHERE id=1").fetchone()[0]

    def capture(self, body: bytes, headers: dict, max_events: int):
        event_id = str(uuid4())
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= max_events:
                raise CapacityError
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                (event_id, now(), json.dumps(headers), body, len(body)),
            )
        return event_id

    def events(self, limit=100, offset=0):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT e.id, e.received_at, e.headers, e.size,"
                " (SELECT COUNT(*) FROM attempts a WHERE a.event_id=e.id) AS attempt_count,"
                " (SELECT status FROM attempts a WHERE a.event_id=e.id"
                " ORDER BY started_at DESC, rowid DESC LIMIT 1) AS last_status"
                " FROM events e ORDER BY received_at DESC, rowid DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) | {"headers": json.loads(row["headers"])} for row in rows]

    def event(self, event_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return dict(row) | {"headers": json.loads(row["headers"])} if row else None

    def attempts(self, event_id):
        with self.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM attempts WHERE event_id=? ORDER BY started_at DESC, rowid DESC",
                    (event_id,),
                )
            ]

    def begin_attempt(self, event_id, target):
        attempt_id = str(uuid4())
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO attempts(id,event_id,target,started_at,status) VALUES(?,?,?,?,?)",
                (attempt_id, event_id, target, now(), "pending"),
            )
        return attempt_id

    def finish_attempt(self, attempt_id, duration_ms, status, status_code, error):
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET duration_ms=?,status=?,status_code=?,error=? WHERE id=?",
                (duration_ms, status, status_code, error, attempt_id),
            )
            return dict(conn.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone())

    def stats(self):
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            counts = dict(conn.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status"))
        return {"events": total, "attempts": sum(counts.values()), "outcomes": counts}
