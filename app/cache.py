import json
import sqlite3
from datetime import datetime

# Bump when the cached response shape changes; old rows stay in SQLite but are
# never read again (the 2026-11-08 contract change made old geometries invalid).
CACHE_VERSION = "v2"


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
        return f"{CACHE_VERSION}|{start}|{end}|{preference or ''}"

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


GEOCODE_TTL_SECONDS = 300  # 5 minutes


class GeocodeCache:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP
                )
            """)
            conn.commit()

    def get(self, key: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, created_at FROM geocode_cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                created_at = datetime.fromisoformat(row[1])
                if (datetime.now() - created_at).total_seconds() <= GEOCODE_TTL_SECONDS:
                    return json.loads(row[0])
        return None

    def set(self, key: str, value: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO geocode_cache (key, value, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), datetime.now())
            )
            conn.commit()