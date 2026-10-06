"""Local message history. The radio does not keep an inbox for us."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


def data_dir() -> Path:
    root = os.environ.get("XDG_DATA_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share"
    path = base / "mesh-desk"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "messages.sqlite")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                channel INTEGER,
                peer TEXT,
                from_id TEXT,
                to_id TEXT,
                text TEXT NOT NULL,
                hops INTEGER,
                outgoing INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def add(
        self,
        *,
        kind: str,
        text: str,
        ts: float | None = None,
        channel: int | None = None,
        peer: str | None = None,
        from_id: str | None = None,
        to_id: str | None = None,
        hops: int | None = None,
        outgoing: bool = False,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO messages (ts, kind, channel, peer, from_id, to_id, text, hops, outgoing)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts if ts is not None else time.time(),
                kind,
                channel,
                peer,
                from_id,
                to_id,
                text,
                hops,
                1 if outgoing else 0,
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def recent_duplicate(self, from_id: str, text: str, within: float = 8.0) -> bool:
        row = self.db.execute(
            """
            SELECT 1 FROM messages
            WHERE from_id = ? AND text = ? AND ts > ?
            LIMIT 1
            """,
            (from_id, text, time.time() - within),
        ).fetchone()
        return row is not None

    def list_channel(self, channel: int, limit: int = 400) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                """
                SELECT * FROM messages
                WHERE kind = 'channel' AND channel = ?
                ORDER BY ts ASC, id ASC
                LIMIT ?
                """,
                (channel, limit),
            )
        )

    def list_dm(self, peer: str, limit: int = 400) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                """
                SELECT * FROM messages
                WHERE kind = 'dm' AND peer = ?
                ORDER BY ts ASC, id ASC
                LIMIT ?
                """,
                (peer, limit),
            )
        )
