"""Deterministic answer text built from real aggregate values."""

from __future__ import annotations

from typing import Any

from .models import QueryPlan


def _fmt_region(plan: QueryPlan) -> str:
    if plan.wmo:
        return f"float WMO {plan.wmo}"
    return plan.basin or "the Indian Ocean domain"


def compose_answer(plan: QueryPlan, stats: dict[str, Any], charts: dict[str, Any]) -> str:
    if stats["profiles"] == 0:
        return (
            f"No QC-passed profiles found for {_fmt_region(plan)} between "
            f"{plan.start_date} and {plan.end_date}. Try widening the date range."
        )

    head = (
        f"Found **{stats['profiles']} profiles** from **{stats['floats']} floats** in "
        f"{_fmt_region(plan)} ({plan.start_date} to {plan.end_date})."
    )
    lines = [head, ""]

    if plan.intent == "salinity_profile":
        halocline = _gradient_depth(charts["salinity_depth"])
        lines += [
            f"- Mean surface salinity: **{stats['mean_sss']} PSU**",
            f"- Strongest salinity gradient near **{halocline} m**",
        ]
    elif plan.intent == "temperature_profile":
        thermocline = _gradient_depth(charts["temperature_depth"])
        lines += [
            f"- Mean SST: **{stats['mean_sst']} °C**",
            f"- Thermocline centred near **{thermocline} m**",
        ]
    elif plan.intent == "oxygen_minimum":
        omz = _min_depth(charts["oxygen_depth"])
        lines += [
            f"- Oxygen minimum at **{omz['depth']} m** ({omz['value']} µmol/kg)",
            "- BGC floats only; QC 4 levels excluded",
        ]
    elif plan.intent == "bgc_comparison":
        chl = _max_depth(charts["chlorophyll_depth"])
        lines += [
            f"- Subsurface chlorophyll maximum at **{chl['depth']} m** ({chl['value']} mg/m³)",
            f"- Mean SST **{stats['mean_sst']} °C**, mean SSS **{stats['mean_sss']} PSU**",
        ]
    elif plan.intent == "nearest_floats" and charts["nearest"]:
        for f in charts["nearest"][:3]:
            lines.append(f"- WMO {f['wmo']} — {f['distance_km']} km ({f['basin']})")
    elif plan.intent == "float_timeseries":
        monthly = charts["monthly"]
        if monthly:
            lines += [
                f"- First cycle {monthly[0]['month']} at {monthly[0]['sst']} °C",
                f"- Latest cycle {monthly[-1]['month']} at {monthly[-1]['sst']} °C",
            ]
    else:
        lines += [
            f"- Mean SST **{stats['mean_sst']} °C**, mean SSS **{stats['mean_sss']} PSU**",
            f"- QC passed: **{stats['qc_passed']}**",
        ]

    lines += ["", "Profiles and float positions are rendered in the console panel."]
    return "\n".join(lines)


def _gradient_depth(curve: list[dict[str, Any]]) -> float:
    if len(curve) < 2:
        return 0
    best = max(
        zip(curve, curve[1:]),
        key=lambda pair: abs(pair[1]["value"] - pair[0]["value"])
        / max(pair[1]["depth"] - pair[0]["depth"], 1),
    )
    return best[1]["depth"]


def _min_depth(curve: list[dict[str, Any]]) -> dict[str, Any]:
    return min(curve, key=lambda p: p["value"]) if curve else {"depth": 0, "value": 0}


def _max_depth(curve: list[dict[str, Any]]) -> dict[str, Any]:
    return max(curve, key=lambda p: p["value"]) if curve else {"depth": 0, "value": 0}
