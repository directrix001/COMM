"""
routers/tab1_mapping.py  — FIXED (NaN/inf JSON serialisation)
"""
from __future__ import annotations

import io
import math
import uuid

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from services import data_helpers as dh
from services import session_store as ss

router = APIRouter()


def _sid(request: Request) -> str:
    return request.cookies.get("va_sid", str(uuid.uuid4()))


# ── Core fix: sanitise every value before JSON serialisation ──────────────
def _safe_value(v):
    """Convert NaN / inf / -inf to None so JSONResponse never chokes."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    # numpy scalar types
    try:
        import numpy as np
        if isinstance(v, (np.floating, np.integer)):
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        if isinstance(v, np.bool_):
            return bool(v)
    except ImportError:
        pass
    return v


def _safe_records(df: pd.DataFrame) -> list:
    """
    Convert DataFrame → list[dict] with ALL NaN / inf replaced by None.
    Works even when df.where(pd.notnull(df), None) misses numpy edge-cases.
    """
    records = []
    for row in df.itertuples(index=False):
        records.append({
            col: _safe_value(getattr(row, col))
            for col in df.columns
        })
    return records


def _sanitise_df(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN / inf in every numeric column before storing in session."""
    df = df.copy()
    for col in df.select_dtypes(include=["float", "float64", "float32"]).columns:
        df[col] = df[col].apply(lambda x: None if (
            x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
        ) else x)
    return df


# ── POST /api/tab1/upload ─────────────────────────────────────────────────

@router.post("/upload")
async def upload_monthly(request: Request, file: UploadFile = File(...)):
    sid = _sid(request)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx / .xls files are accepted.")

    file_bytes = await file.read()

    try:
        df_final = dh.generate_mapping(file_bytes)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Mapping error: {exc}")

    # ── Sanitise BEFORE storing and before building preview ──────────────
    df_final = _sanitise_df(df_final)

    # Store in session (orient="split" handles None correctly)
    ss.set(sid, "final_db_bytes", df_final.to_json(orient="split"))

    preview = df_final.head(100)

    response_data = {
        "session_id": sid,
        "rows":       len(df_final),
        "columns":    df_final.columns.tolist(),
        "preview":    _safe_records(preview),   # ← uses safe serialiser
        "warnings":   _check_mapping_warnings(),
    }

    resp = JSONResponse(content=response_data)
    resp.set_cookie("va_sid", sid, httponly=True, samesite="lax")
    return resp


def _check_mapping_warnings() -> list:
    import os
    from services.data_helpers import MAPPING_PATH
    warnings = []
    if not os.path.exists(MAPPING_PATH):
        warnings.append("mapping.xlsx not found — output has no Region/Market enrichment.")
    return warnings


# ── GET /api/tab1/download/csv ────────────────────────────────────────────

@router.get("/download/csv")
async def download_csv(request: Request):
    sid = _sid(request)
    df  = _load_session_df(sid)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mapping_output.csv"},
    )


# ── GET /api/tab1/download/xlsx ───────────────────────────────────────────

@router.get("/download/xlsx")
async def download_xlsx(request: Request):
    sid = _sid(request)
    df  = _load_session_df(sid)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="mapping_output")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=mapping_output.xlsx"},
    )


# ── Helper ────────────────────────────────────────────────────────────────

def _load_session_df(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "final_db_bytes")
    if raw is None:
        raise HTTPException(404, "No mapping data in session. Upload a file first.")
    return pd.read_json(io.StringIO(raw), orient="split")
