import json
import sqlite3


class Cache:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS route_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _make_key(self, start: str, end: str, preference: str | None) -> str:
        return f"{start}|{end}|{preference or ''}"

    def get(self, key: tuple[str, str, str | None]) -> dict | None:
        start, end, preference = key
        db_key = self._make_key(start, end, preference)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM route_cache WHERE key = ?", (db_key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def set(self, key: tuple[str, str, str | None], value: dict) -> None:
        start, end, preference = key
        db_key = self._make_key(start, end, preference)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO route_cache (key, value) VALUES (?, ?)",
                (db_key, json.dumps(value))
            )
            conn.commit()