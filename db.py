"""SQLite storage + synthetic ARGO seed data for FloatChat."""

from __future__ import annotations

import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "floatchat.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS floats (
    wmo         TEXT PRIMARY KEY,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    basin       TEXT NOT NULL,
    is_bgc      INTEGER NOT NULL DEFAULT 0,
    last_cycle  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wmo         TEXT NOT NULL REFERENCES floats(wmo) ON DELETE CASCADE,
    cycle       INTEGER NOT NULL,
    profile_date TEXT NOT NULL,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    sst         REAL NOT NULL,
    sss         REAL NOT NULL,
    qc          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS levels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    depth       REAL NOT NULL,
    temperature REAL NOT NULL,
    salinity    REAL NOT NULL,
    oxygen      REAL,
    chlorophyll REAL
);

CREATE INDEX IF NOT EXISTS idx_profiles_wmo ON profiles(wmo);
CREATE INDEX IF NOT EXISTS idx_profiles_date ON profiles(profile_date);
CREATE INDEX IF NOT EXISTS idx_levels_profile ON levels(profile_id);
"""

DEPTHS = [0, 10, 20, 30, 50, 75, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000]

BASINS = {
    "Arabian Sea": ((5.0, 24.0), (55.0, 76.0)),
    "Bay of Bengal": ((5.0, 22.0), (80.0, 95.0)),
    "Equatorial Indian": ((-5.0, 5.0), (60.0, 95.0)),
    "Southern Indian": ((-35.0, -6.0), (50.0, 100.0)),
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def _level_values(depth: float, sst: float, sss: float, bgc: bool) -> tuple[float, float, float | None, float | None]:
    # Thermocline: exponential decay toward ~3 degC in the deep ocean.
    temperature = 3.0 + (sst - 3.0) * math.exp(-depth / 320.0)
    # Halocline near 80 m, then slow increase with depth.
    salinity = sss + 0.45 * (1 - math.exp(-depth / 90.0)) - 0.0001 * depth
    oxygen = chlorophyll = None
    if bgc:
        # Oxygen minimum zone between ~150 and 800 m.
        oxygen = max(3.0, 205.0 * math.exp(-((depth - 20) ** 2) / 26000.0) + 18.0 + depth / 260.0)
        chlorophyll = round(max(0.02, 0.9 * math.exp(-((depth - 45) ** 2) / 2200.0)), 3)
    return round(temperature, 2), round(salinity, 3), (round(oxygen, 1) if oxygen else None), chlorophyll


def _create_float(conn: sqlite3.Connection, i: int, rng: random.Random, start: date) -> tuple[str, str, float, float, int, int]:
    """Create a float record and return (wmo, basin, lat, lon, is_bgc, n_cycles)."""
    basin = list(BASINS)[i % len(BASINS)]
    (lat_lo, lat_hi), (lon_lo, lon_hi) = BASINS[basin]
    lat = round(rng.uniform(lat_lo, lat_hi), 3)
    lon = round(rng.uniform(lon_lo, lon_hi), 3)
    wmo = str(2900000 + i * 137 + rng.randint(1, 99))
    is_bgc = 1 if i % 3 == 0 else 0
    n_cycles = rng.randint(10, 18)
    last = start + timedelta(days=10 * n_cycles)
    active = 1 if rng.random() > 0.2 else 0

    conn.execute(
        "INSERT INTO floats (wmo, lat, lon, basin, is_bgc, last_cycle, active)"
        " VALUES (?,?,?,?,?,?,?)",
        (wmo, lat, lon, basin, is_bgc, last.isoformat(), active),
    )
    return wmo, basin, lat, lon, is_bgc, n_cycles


def _create_profiles(conn: sqlite3.Connection, wmo: str, basin: str, lat: float, lon: float, is_bgc: int, n_cycles: int, rng: random.Random, start: date) -> None:
    """Create all profile records for a float."""
    for cycle in range(1, n_cycles + 1):
        d = start + timedelta(days=10 * cycle)
        drift_lat = round(lat + rng.uniform(-1.2, 1.2), 3)
        drift_lon = round(lon + rng.uniform(-1.2, 1.2), 3)
        seasonal = 1.4 * math.sin((d.timetuple().tm_yday / 365) * 2 * math.pi)
        sst = round(28.6 + seasonal - abs(drift_lat) * 0.06 + rng.uniform(-0.5, 0.5), 2)
        if basin == "Arabian Sea":
            basin_offset = 0.5
        elif basin == "Bay of Bengal":
            basin_offset = -0.35
        else:
            basin_offset = 0.0
        sss = round(34.2 + basin_offset + rng.uniform(-0.15, 0.15), 3)
        qc = 4 if rng.random() < 0.03 else 1
        cur = conn.execute(
            "INSERT INTO profiles (wmo, cycle, profile_date, lat, lon, sst, sss, qc)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (wmo, cycle, d.isoformat(), drift_lat, drift_lon, sst, sss, qc),
        )
        profile_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO levels (profile_id, depth, temperature, salinity, oxygen, chlorophyll)"
            " VALUES (?,?,?,?,?,?)",
            [(profile_id, depth, *_level_values(depth, sst, sss, bool(is_bgc))) for depth in DEPTHS],
        )


def seed(reset: bool = False) -> None:
    """Create the schema and populate deterministic synthetic ARGO data."""
    if reset and DB_PATH.exists():
        DB_PATH.unlink()

    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) AS n FROM floats").fetchone()["n"]:
            conn.close()
            return

        rng = random.Random(20240317)
        start = date(2023, 1, 1)
        for i in range(48):
            wmo, basin, lat, lon, is_bgc, n_cycles = _create_float(conn, i, rng, start)
            _create_profiles(conn, wmo, basin, lat, lon, is_bgc, n_cycles, rng, start)
    conn.close()



