"""Aggregations that back the dashboard stats, charts and data table."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from statistics import mean
from typing import Any

from .db import connect, rows_to_dicts
from .models import QueryPlan


def run_plan(plan: QueryPlan) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(plan.sql, tuple(plan.params)).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def summary_stats(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not profiles:
        return {"floats": 0, "profiles": 0, "mean_sss": None, "mean_sst": None, "qc_passed": "0%"}
    return {
        "floats": len({p["wmo"] for p in profiles}),
        "profiles": len(profiles),
        "mean_sss": round(mean(p["sss"] for p in profiles), 2),
        "mean_sst": round(mean(p["sst"] for p in profiles), 2),
        "qc_passed": f"{100 * sum(p['qc'] == 1 for p in profiles) / len(profiles):.1f}%",
    }


def _levels_for(conn: sqlite3.Connection, profile_ids: list[int]) -> list[sqlite3.Row]:
    if not profile_ids:
        return []
    placeholders = ",".join("?" * len(profile_ids))
    return conn.execute(
        f"SELECT depth, temperature, salinity, oxygen, chlorophyll FROM levels"
        f" WHERE profile_id IN ({placeholders})",
        tuple(profile_ids),
    ).fetchall()


def depth_curves(profile_ids: list[int]) -> dict[str, list[dict[str, Any]]]:
    """Mean value per standard depth level: temperature, salinity, oxygen, chl-a."""
    conn = connect()
    try:
        rows = _levels_for(conn, profile_ids[:120])
    finally:
        conn.close()

    buckets: dict[float, dict[str, list[float]]] = defaultdict(
        lambda: {"temperature": [], "salinity": [], "oxygen": [], "chlorophyll": []}
    )
    for r in rows:
        for key in ("temperature", "salinity", "oxygen", "chlorophyll"):
            if r[key] is not None:
                buckets[r["depth"]][key].append(r[key])

    out: dict[str, list[dict[str, Any]]] = {
        "temperature": [], "salinity": [], "oxygen": [], "chlorophyll": []
    }
    for depth in sorted(buckets):
        for key, values in buckets[depth].items():
            if values:
                out[key].append({"depth": depth, "value": round(mean(values), 3)})
    return out


def ts_diagram(profile_ids: list[int], limit: int = 220) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = _levels_for(conn, profile_ids[:60])
    finally:
        conn.close()
    return [
        {"temperature": r["temperature"], "salinity": r["salinity"], "depth": r["depth"]}
        for r in rows[:limit]
    ]


def monthly_series(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in profiles:
        buckets[p["profile_date"][:7]].append(p)
    return [
        {
            "month": month,
            "sst": round(mean(x["sst"] for x in items), 2),
            "sss": round(mean(x["sss"] for x in items), 3),
            "profiles": len(items),
        }
        for month, items in sorted(buckets.items())
    ]


def basin_heat_content() -> list[dict[str, Any]]:
    """Proxy 0-700 m ocean heat content per basin, from mean temperature."""
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT f.basin AS basin, AVG(l.temperature) AS mean_temp, COUNT(*) AS n
            FROM levels l
            JOIN profiles p ON p.id = l.profile_id
            JOIN floats f ON f.wmo = p.wmo
            WHERE l.depth <= 700
            GROUP BY f.basin
            ORDER BY mean_temp DESC
            """
        ).fetchall()
    finally:
        conn.close()
    # rho * cp * dz  ~= 1025 * 3850 * 700 J/m2/K -> ZJ-scale proxy value.
    return [
        {
            "basin": r["basin"],
            "mean_temp": round(r["mean_temp"], 2),
            "ohc_proxy_gj_m2": round(1025 * 3850 * 700 * r["mean_temp"] / 1e9, 1),
            "levels": r["n"],
        }
        for r in rows
    ]


def nearest_floats(lat: float, lon: float, limit: int = 8) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM floats").fetchall()
    finally:
        conn.close()
    scored = [
        {**dict(r), "distance_km": round(_haversine(lat, lon, r["lat"], r["lon"]), 1)}
        for r in rows
    ]
    scored.sort(key=lambda r: r["distance_km"])
    return scored[:limit]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


def build_charts(plan: QueryPlan, profiles: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [p["id"] for p in profiles]
    curves = depth_curves(ids)
    return {
        "temperature_depth": curves["temperature"],
        "salinity_depth": curves["salinity"],
        "oxygen_depth": curves["oxygen"],
        "chlorophyll_depth": curves["chlorophyll"],
        "ts_diagram": ts_diagram(ids),
        "monthly": monthly_series(profiles),
        "heat_content": basin_heat_content(),
        "float_positions": [
            {"wmo": p["wmo"], "lat": p["lat"], "lon": p["lon"], "date": p["profile_date"]}
            for p in profiles[:200]
        ],
        "nearest": nearest_floats(plan.lat, plan.lon) if plan.lat is not None and plan.lon is not None else [],
    }