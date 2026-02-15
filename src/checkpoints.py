from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class CheckpointStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    dataset TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (dataset, scope)
                )
                """
            )
            conn.commit()

    def get(self, dataset: str, scope: str) -> Optional[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT status, payload_json, updated_at FROM checkpoints WHERE dataset=? AND scope=?",
                (dataset, scope),
            )
            row = cur.fetchone()
            if not row:
                return None
            status, payload_json, updated_at = row
            payload = json.loads(payload_json)
            return {"status": status, "payload": payload, "updated_at": updated_at}

    def upsert(
        self,
        dataset: str,
        scope: str,
        status: str,
        payload: dict[str, Any],
        updated_at: str,
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (dataset, scope, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(dataset, scope)
                DO UPDATE SET status=excluded.status, payload_json=excluded.payload_json, updated_at=excluded.updated_at
                """,
                (dataset, scope, status, payload_json, updated_at),
            )
            conn.commit()
