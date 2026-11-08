"""SQLite-backed cache for weather payloads."""

import json
import sqlite3
from datetime import UTC, datetime


class WeatherCache:
    """Cache weather payloads keyed by string, with a time-to-live."""

    def __init__(self, db_path="weather_cache.db", ttl_seconds=1800):
        """Initialize the cache and ensure the backing table exists."""
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _init_db(self):
        """Create the weather_cache table if it does not already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_cache(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _make_key(self, lat: float, lng: float) -> str:
        """Build a cache key from coordinates rounded to 2 decimals."""
        return f"weather|{round(lat, 2):.2f}|{round(lng, 2):.2f}"

    def get(self, lat: float, lng: float) -> dict | None:
        """Return the cached weather payload for coordinates, or None if missing/expired."""
        key = self._make_key(lat, lng)
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT value, created_at FROM weather_cache WHERE key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    return None
                value, created_at = row
                if created_at is None:
                    return None
                age = conn.execute(
                    "SELECT julianday('now') - julianday(?)", (created_at,)
                ).fetchone()[0]
        except sqlite3.Error:
            return None
        if age is None or age * 86400 > self.ttl_seconds:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def set(self, lat: float, lng: float, data: dict) -> None:
        """Store a weather payload for coordinates, replacing any existing entry."""
        key = self._make_key(lat, lng)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO weather_cache(key, value, created_at)"
                    " VALUES (?, ?, ?)",
                    (key, json.dumps(data), datetime.now(UTC).isoformat()),
                )
        except sqlite3.Error:
            return
