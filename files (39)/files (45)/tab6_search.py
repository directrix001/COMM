"""
routers/tab6_search.py  — FIXED (NaN/inf JSON serialisation)
"""
from __future__ import annotations

import io
import math
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services import session_store as ss

router = APIRouter()

MASTER_XLSX = Path("database") / "Segregateddata.xlsx"
FILTER_COLS = [
    "Category", "Scenarios", "Functions", "Functions-View",
    "Year", "Month", "Region", "Criteria",
]


def _sid(request: Request) -> str:
    return request.cookies.get("va_sid", str(uuid.uuid4()))


# ── Sanitise helpers ──────────────────────────────────────────────────────

def _safe_value(v):
    """NaN / inf / numpy scalars → None or plain Python type."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    try:
        import numpy as np
        if isinstance(v, (np.floating, np.integer)):
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        if isinstance(v, np.bool_):
            return bool(v)
    except ImportError:
        pass
    return v


def _safe_records(df: pd.DataFrame) -> list:
    """Uses iloc — safe for column names containing spaces or special chars."""
    cols = df.columns.tolist()
    result = []
    for i in range(len(df)):
        row_dict = {}
        for j, col in enumerate(cols):
            row_dict[col] = _safe_value(df.iloc[i, j])
        result.append(row_dict)
    return result


def _sanitise_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce all columns to safe types:
    - String filter columns → str, NaN → ""
    - Numeric columns → NaN/inf replaced with None (stored as object)
    - Object columns → NaN → ""
    """
    df = df.copy()

    # Force filter + text columns to clean strings
    for col in FILTER_COLS + ["Comments"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "").replace("None", "")

    # Fix remaining float columns
    for col in df.select_dtypes(include=["float", "float64", "float32"]).columns:
        df[col] = df[col].apply(
            lambda x: None if (x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))) else x
        )

    # Fix object columns with stray NaN
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: "" if (x is None or (isinstance(x, float) and math.isnan(x))) else x
        )

    return df


# ── Load master DB ────────────────────────────────────────────────────────

def _load_master() -> pd.DataFrame:
    if not MASTER_XLSX.exists():
        raise HTTPException(
            404,
            f"Master database not found at '{MASTER_XLSX}'. "
            "Use the PPT Upload tab to push data first."
        )
    try:
        df = pd.read_excel(MASTER_XLSX)
        return _sanitise_df(df)      # ← sanitise on load, once
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Error reading master database: {exc}")


# ── GET /api/tab6/filters ─────────────────────────────────────────────────

@router.get("/filters")
async def get_filters():
    df = _load_master()

    opts: dict[str, list] = {}
    for col in FILTER_COLS:
        if col in df.columns:
            # Already strings after _sanitise_df; filter blanks
            vals = sorted({v for v in df[col].tolist() if v and v.strip() and v != "nan"})
            opts[col] = vals

    return JSONResponse({
        "filter_cols": FILTER_COLS,
        "options":     opts,
        "total_rows":  len(df),
    })


# ── POST /api/tab6/search ─────────────────────────────────────────────────

@router.post("/search")
async def search(request: Request):
    """
    Body JSON:
    {
      "search_text": "keyword",
      "filters": { "Category": ["G&A"], "Month": ["January"] }
    }
    """
    sid  = _sid(request)
    body = await request.json()

    df = _load_master()

    # Apply column filters
    for col, vals in (body.get("filters") or {}).items():
        if vals and col in df.columns:
            df = df[df[col].isin(vals)]

    # Apply free-text search on Comments
    q = (body.get("search_text") or "").strip()
    if q and "Comments" in df.columns:
        df = df[df["Comments"].str.contains(q, case=False, na=False)]

    # Store for download (reset index so orient=split is clean)
    df_save = df.reset_index(drop=True)
    ss.set(sid, "search_result_bytes", df_save.to_json(orient="split"))

    return JSONResponse({
        "columns": df.columns.tolist(),
        "records": _safe_records(df.head(500)),   # cap display at 500
        "count":   len(df),
    })


# ── GET /api/tab6/download/csv ────────────────────────────────────────────

@router.get("/download/csv")
async def download_csv(request: Request):
    sid = _sid(request)
    df  = _get_result_df(sid)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Filtered_Commentary.csv"},
    )


# ── GET /api/tab6/download/xlsx ───────────────────────────────────────────

@router.get("/download/xlsx")
async def download_xlsx(request: Request):
    sid = _sid(request)
    df  = _get_result_df(sid)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Filtered")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Filtered_Commentary.xlsx"},
    )


# ── Helper ────────────────────────────────────────────────────────────────

def _get_result_df(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "search_result_bytes")
    if not raw:
        raise HTTPException(404, "No search result in session. Run a search first.")
    return pd.read_json(io.StringIO(raw), orient="split")
