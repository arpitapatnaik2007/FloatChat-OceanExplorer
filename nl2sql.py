"""Rule-based natural-language → SQL planner for ARGO questions.

Deterministic and dependency-free so the API works offline. If an LLM key is
configured (see ``llm.py``) the answer text is polished by the model, but the
SQL plan below always decides what data is actually read.
"""

from __future__ import annotations

import re
from datetime import date

from .models import QueryPlan

BASIN_KEYWORDS = {
    "Arabian Sea": ("arabian", "arabia", "अरब", "ଆରବ"),
    "Bay of Bengal": ("bengal", "bob", "बंगाल", "ବଙ୍ଗୋପସାଗର"),
    "Equatorial Indian": ("equator", "equatorial", "भूमध्य", "ବିଷୁବ"),
    "Southern Indian": ("southern", "south indian", "दक्षिण"),
}

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
    )
}

PROFILE_SQL = """
SELECT p.id, p.wmo, p.cycle, p.profile_date, p.lat, p.lon, p.sst, p.sss, p.qc
FROM profiles p
JOIN floats f ON f.wmo = p.wmo
WHERE p.qc = 1
  {basin_clause}
  {wmo_clause}
  {bgc_clause}
  AND p.profile_date BETWEEN ? AND ?
ORDER BY p.profile_date
LIMIT 500
""".strip()


def _detect_basin(text: str) -> str | None:
    for basin, keys in BASIN_KEYWORDS.items():
        if any(k in text for k in keys):
            return basin
    return None


def _detect_dates(text: str) -> tuple[str, str]:
    year_match = re.search(r"(19|20)\d{2}", text)
    year = int(year_match.group()) if year_match else 2023
    for name, num in MONTHS.items():
        if name in text:
            start = date(year, num, 1)
            end = date(year + (num == 12), (num % 12) + 1, 1)
            return start.isoformat(), end.isoformat()
    months_back = re.search(r"last\s+(\d+)\s+month", text)
    if months_back:
        n = min(int(months_back.group(1)), 36)
        end = date(year, 12, 31)
        start = date(year, max(1, 12 - n + 1), 1)
        return start.isoformat(), end.isoformat()
    return date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()


def _detect_intent(text: str) -> str:
    if "wmo" in text or re.search(r"\b29\d{5}\b", text):
        return "float_timeseries"
    if "nearest" in text or "closest" in text:
        return "nearest_floats"
    if "oxygen" in text or "omz" in text or "minimum zone" in text:
        return "oxygen_minimum"
    if "bgc" in text or "chlorophyll" in text or "biogeo" in text:
        return "bgc_comparison"
    if "salinity" in text or "psu" in text or "halocline" in text:
        return "salinity_profile"
    if "temperature" in text or "sst" in text or "thermocline" in text or "warming" in text:
        return "temperature_profile"
    return "overview"


def _detect_coords(text: str) -> tuple[float | None, float | None]:
    coords = re.findall(r"(-?\d+(?:\.\d+)?)\s*°?\s*([NSEW])", text, flags=re.I)
    lat = lon = None
    for value, hemi in coords:
        v = float(value)
        h = hemi.upper()
        if h in "NS":
            lat = v if h == "N" else -v
        else:
            lon = v if h == "E" else -v
    return lat, lon


def plan_query(message: str) -> QueryPlan:
    text = message.lower()
    intent = _detect_intent(text)
    basin = _detect_basin(text)
    start_date, end_date = _detect_dates(text)
    lat, lon = _detect_coords(text)
    wmo_match = re.search(r"\b(\d{7})\b", text)
    wmo = wmo_match.group(1) if wmo_match else None

    params: list[object] = []
    basin_clause = ""
    if basin:
        basin_clause = "AND f.basin = ?"
        params.append(basin)

    wmo_clause = ""
    if wmo:
        wmo_clause = "AND p.wmo = ?"
        params.append(wmo)

    bgc_clause = "AND f.is_bgc = 1" if intent in {"bgc_comparison", "oxygen_minimum"} else ""

    params.extend([start_date, end_date])
    sql = PROFILE_SQL.format(
        basin_clause=basin_clause, wmo_clause=wmo_clause, bgc_clause=bgc_clause
    )

    return QueryPlan(
        intent=intent,
        basin=basin,
        wmo=wmo,
        start_date=start_date,
        end_date=end_date,
        lat=lat,
        lon=lon,
        sql=sql,
        params=params,
    )
