"""FloatChat backend — FastAPI service for ARGO ocean data discovery.


Run:  uvicorn app.main:app --reload --port 8000   (from the backend/ folder)
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import csv
import io
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Query  # type: ignore[import-not-found]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[import-not-found]
from fastapi.responses import StreamingResponse  # type: ignore[import-not-found]

from . import analytics
from .answers import compose_answer
from .db import connect, rows_to_dicts, seed
from .languages import LANGUAGES, resolve
from .llm import polish
from .models import (
    ChatRequest,
    ChatResponse,
    FloatOut,
    LanguageOut,
    ProfileDetail,
    ProfileOut,
)
from .nl2sql import plan_query

app = FastAPI(
    title="FloatChat API",
    version="1.0.0",
    description="Conversational discovery and visualisation of ARGO ocean float data.",
)

ALLOWED_ORIGINS = os.getenv(
    "FLOATCHAT_CORS_ORIGINS",
    "http://localhost:8080,http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    seed()


@app.get("/api/health")
def health() -> dict[str, Any]:
    conn = connect()
    try:
        floats = conn.execute("SELECT COUNT(*) AS n FROM floats").fetchone()["n"]
        profiles = conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"]
    finally:
        conn.close()
    return {"status": "ok", "floats": floats, "profiles": profiles}


@app.get("/api/languages", response_model=list[LanguageOut])
def languages() -> list[dict[str, str]]:
    return LANGUAGES


@app.get("/api/floats", response_model=list[FloatOut])
def list_floats(
    basin: str | None = None,
    bgc_only: bool = False,
    active_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM floats WHERE 1=1"
    params: list[Any] = []
    if basin:
        sql += " AND basin = ?"
        params.append(basin)
    if bgc_only:
        sql += " AND is_bgc = 1"
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY wmo LIMIT ?"
    params.append(limit)

    conn = connect()
    try:
        return rows_to_dicts(conn.execute(sql, tuple(params)).fetchall())
    finally:
        conn.close()
@app.get(
    "/api/floats/{wmo}/profiles",
    response_model=list[ProfileOut],
    responses={404: {"description": "Unknown float WMO"}},
)
def float_profiles(wmo: str, limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    conn = connect()
    try:
        if not conn.execute("SELECT 1 FROM floats WHERE wmo = ?", (wmo,)).fetchone():
            raise HTTPException(status_code=404, detail=f"Unknown float WMO {wmo}")
        return rows_to_dicts(
            conn.execute(
                "SELECT id, wmo, cycle, profile_date, lat, lon, sst, sss, qc FROM profiles"
                " WHERE wmo = ? ORDER BY cycle LIMIT ?",
                (wmo, limit),
            ).fetchall()
        )
    finally:
        conn.close()


@app.get("/api/profiles/{profile_id}", response_model=ProfileDetail, responses={404: {"description": "Profile not found"}})
def profile_detail(profile_id: int) -> dict[str, Any]:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, wmo, cycle, profile_date, lat, lon, sst, sss, qc FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        levels = conn.execute(
            "SELECT depth, temperature, salinity, oxygen, chlorophyll FROM levels"
            " WHERE profile_id = ? ORDER BY depth",
            (profile_id,),
        ).fetchall()
    finally:
        conn.close()
    return {**dict(row), "levels": rows_to_dicts(levels)}


@app.get("/api/charts/overview")
def charts_overview(
    basin: str | None = None,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
) -> dict[str, Any]:
    """All dashboard chart series for a region/date window."""
    plan = plan_query(
        f"overview {basin or ''} {start_date[:4]}".strip()
    )
    plan.basin = basin
    plan.start_date, plan.end_date = start_date, end_date
    plan.params = ([basin] if basin else []) + [start_date, end_date]
    if not basin:
        plan.sql = plan.sql.replace("AND f.basin = ?", "")
    profiles = analytics.run_plan(plan)
    return {
        "stats": analytics.summary_stats(profiles),
        "charts": analytics.build_charts(plan, profiles),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> dict[str, Any]:
    """Natural-language question → SQL plan → data → narrated answer."""
    plan = plan_query(req.message)
    profiles = analytics.run_plan(plan)
    stats = analytics.summary_stats(profiles)
    charts = analytics.build_charts(plan, profiles)

    lang = resolve(req.language)
    answer = compose_answer(plan, stats, charts)
    answer = await polish(answer, req.message, lang["label"])

    return {
        "session_id": req.session_id or str(uuid.uuid4()),
        "answer": answer,
        "plan": plan,
        "stats": stats,
        "charts": charts,
        "table": profiles[:50],
        "citations": [
            "ARGO global float array — Indian Ocean subset",
            f"intent={plan.intent}; window={plan.start_date}..{plan.end_date}",
        ],
    }
@app.get("/api/export.csv")
def export_csv(
    basin: str | None = None,
    wmo: str | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
) -> StreamingResponse:
    sql = (
        "SELECT p.wmo, p.cycle, p.profile_date, p.lat, p.lon, p.sst, p.sss, p.qc, f.basin"
        " FROM profiles p JOIN floats f ON f.wmo = p.wmo WHERE 1=1"
    )
    params: list[Any] = []
    if basin:
        sql += " AND f.basin = ?"
        params.append(basin)
    if wmo:
        sql += " AND p.wmo = ?"
        params.append(wmo)
    sql += " ORDER BY p.profile_date LIMIT ?"
    params.append(limit)

    conn = connect()
    try:
        rows = rows_to_dicts(conn.execute(sql, tuple(params)).fetchall())
    finally:
        conn.close()

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["wmo", "cycle", "profile_date", "lat", "lon", "sst", "sss", "qc", "basin"],
    )
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="floatchat_profiles.csv"'},
    )
