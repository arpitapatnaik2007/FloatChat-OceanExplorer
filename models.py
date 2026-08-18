"""Pydantic request/response models for the FloatChat API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FloatOut(BaseModel):
    wmo: str
    lat: float
    lon: float
    basin: str
    is_bgc: bool
    last_cycle: str
    active: bool


class ProfileOut(BaseModel):
    id: int
    wmo: str
    cycle: int
    profile_date: str
    lat: float
    lon: float
    sst: float
    sss: float
    qc: int


class LevelOut(BaseModel):
    depth: float
    temperature: float
    salinity: float
    oxygen: float | None = None
    chlorophyll: float | None = None


class ProfileDetail(ProfileOut):
    levels: list[LevelOut]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: str = Field(default="en-IN", max_length=12)
    session_id: str | None = Field(default=None, max_length=64)


class QueryPlan(BaseModel):
    """What the natural-language question was understood to mean."""

    intent: Literal[
        "salinity_profile",
        "temperature_profile",
        "bgc_comparison",
        "nearest_floats",
        "float_timeseries",
        "oxygen_minimum",
        "overview",
    ]
    basin: str | None = None
    wmo: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    lat: float | None = None
    lon: float | None = None
    sql: str
    params: list[Any] = []


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    plan: QueryPlan
    stats: dict[str, Any]
    charts: dict[str, Any]
    table: list[dict[str, Any]]
    citations: list[str]


class LanguageOut(BaseModel):
    code: str
    label: str
    placeholder: str