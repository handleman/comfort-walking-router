"""Durable run journal — ADR-012 option C, first slice.

The harness already records telemetry (`events.jsonl`) and a per-step snapshot
(`progress.json`), but neither is an authority: a crash between a step and its
checkpoint re-runs the step, and a duplicated commit is prevented by inspection,
not by an idempotency key.

This module is the kernel the ADR describes, scoped to what the flow can use
today:

- an append-only `events` table with an idempotency key per `(run_id, key)`;
- a `steps` table with a status, attempt and lease (claim/heartbeat/expire);
- an `effects` table keyed by a stable effect key (commit/merge/push/approval),
  so a retry is a no-op and the result is replayable;
- `fold(run_id)`: status, completed steps and effects are a projection of the
  journal, not a second source of truth.

SQLite in WAL mode with one writer is enough for the single-machine pilot;
Postgres is the ADR's trigger for real workers (023).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  at REAL NOT NULL,
  type TEXT NOT NULL,
  step TEXT NOT NULL DEFAULT '',
  attempt INTEGER NOT NULL DEFAULT 0,
  key TEXT DEFAULT '',
  payload TEXT NOT NULL DEFAULT '{}',
  UNIQUE(run_id, key)
);
CREATE TABLE IF NOT EXISTS steps(
  run_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  attempt INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_until REAL NOT NULL DEFAULT 0,
  output_digest TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(run_id, idx)
);
CREATE TABLE IF NOT EXISTS effects(
  key TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  result TEXT NOT NULL DEFAULT '{}',
  at REAL NOT NULL
);
"""


@dataclass(frozen=True)
class Step:
    idx: int
    status: str
    attempt: int
    output: str


class Journal:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # ---- events (append-only, idempotent by key) ----

    def append(
        self,
        run_id: str,
        kind: str,
        *,
        step: str = "",
        attempt: int = 0,
        key: str = "",
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Append one event; a repeated `key` is a no-op. Returns whether it wrote."""
        try:
            self._db.execute(
                "INSERT INTO events(run_id, at, type, step, attempt, key, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, time.time(), kind, step, attempt, key or None, json.dumps(payload or {})),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT seq, at, type, step, attempt, key, payload FROM events "
            "WHERE run_id=? ORDER BY seq",
            (run_id,),
        ).fetchall()
        return [
            {
                "seq": r[0], "at": r[1], "type": r[2], "step": r[3],
                "attempt": r[4], "key": r[5], "payload": json.loads(r[6]),
            }
            for r in rows
        ]

    # ---- steps (claim, complete, expire) ----

    def seed_steps(self, run_id: str, count: int) -> None:
        for idx in range(1, count + 1):
            self._db.execute(
                "INSERT OR IGNORE INTO steps(run_id, idx) VALUES (?, ?)", (run_id, idx)
            )
        self._db.commit()

    def claim_step(self, run_id: str, idx: int, owner: str, ttl: float = 300.0) -> bool:
        now = time.time()
        cur = self._db.execute(
            "UPDATE steps SET status='running', attempt=attempt+1, lease_owner=?, "
            "lease_until=? WHERE run_id=? AND idx=? AND status != 'done' "
            "AND (status='queued' OR lease_until<?)",
            (owner, now + ttl, run_id, idx, now),
        )
        self._db.commit()
        return cur.rowcount == 1

    def heartbeat(self, run_id: str, idx: int, owner: str, ttl: float = 300.0) -> bool:
        cur = self._db.execute(
            "UPDATE steps SET lease_until=? WHERE run_id=? AND idx=? AND lease_owner=?",
            (time.time() + ttl, run_id, idx, owner),
        )
        self._db.commit()
        return cur.rowcount == 1

    def complete_step(self, run_id: str, idx: int, output: str) -> None:
        digest = __import__("hashlib").sha256(output.encode()).hexdigest()
        self._db.execute(
            "UPDATE steps SET status='done', lease_owner='', lease_until=0, output_digest=? "
            "WHERE run_id=? AND idx=?",
            (digest, run_id, idx),
        )
        self._db.commit()
        self.append(
            run_id,
            "step_done",
            step=f"step-{idx}",
            key=f"step:{idx}",
            payload={"output": output[-2000:], "digest": digest},
        )

    def steps(self, run_id: str) -> list[Step]:
        rows = self._db.execute(
            "SELECT idx, status, attempt, output_digest FROM steps WHERE run_id=? ORDER BY idx",
            (run_id,),
        ).fetchall()
        events = {e["step"]: e["payload"] for e in self.events(run_id) if e["type"] == "step_done"}
        return [
            Step(idx=r[0], status=r[1], attempt=r[2], output=str(events.get(f"step-{r[0]}", {}).get("output", "")))
            for r in rows
        ]

    def completed_outputs(self, run_id: str) -> list[str]:
        """Outputs of the contiguous completed prefix (for resume)."""
        out: list[str] = []
        for step in self.steps(run_id):
            if step.status != "done":
                break
            out.append(step.output)
        return out

    # ---- effects (idempotent side effects) ----

    def effect(self, key: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT result FROM effects WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def record_effect(self, key: str, run_id: str, kind: str, result: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO effects(key, run_id, kind, result, at) VALUES (?, ?, ?, ?, ?)",
            (key, run_id, kind, json.dumps(result), time.time()),
        )
        self._db.commit()

    # ---- projection ----

    def fold(self, run_id: str) -> dict[str, Any]:
        events = self.events(run_id)
        status = "init"
        for event in events:
            if event["type"] == "run_status":
                status = str(event["payload"].get("status") or status)
        effects = self._db.execute(
            "SELECT key, kind, result FROM effects WHERE run_id=? ORDER BY at", (run_id,)
        ).fetchall()
        return {
            "status": status,
            "events": len(events),
            "steps": [{"idx": s.idx, "status": s.status, "attempt": s.attempt} for s in self.steps(run_id)],
            "effects": [{"key": k, "kind": kind, "result": json.loads(r)} for k, kind, r in effects],
        }
