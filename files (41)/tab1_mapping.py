"""
routers/tab1_mapping.py
────────────────────────
Tab 1 — Tagetik Mapping  (FastAPI router)

Endpoints
---------
POST /api/tab1/upload        Upload monthly Excel → run mapping → return preview + stats
GET  /api/tab1/download/csv  Download mapped CSV
GET  /api/tab1/download/xlsx Download mapped Excel
"""

from __future__ import annotations

import io
import uuid

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from services import data_helpers as dh
from services import session_store as ss

router = APIRouter()


def _sid(request: Request) -> str:
    """Extract or create a session-id from cookie."""
    return request.cookies.get("va_sid", str(uuid.uuid4()))


# ── POST /api/tab1/upload ────────────────────────────────────────────────────

@router.post("/upload")
async def upload_monthly(request: Request, file: UploadFile = File(...)):
    """
    Accepts the monthly Excel file, runs the mapping pipeline,
    stores result in session, returns preview data + column names.
    """
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

    # Store in session
    ss.set(sid, "final_db_bytes", df_final.to_json(orient="split"))

    # Build preview (first 100 rows)
    preview = df_final.head(100)
    response_data = {
        "session_id": sid,
        "rows":       len(df_final),
        "columns":    df_final.columns.tolist(),
        "preview":    dh.df_to_records(preview),
        "warnings":   _check_mapping_warnings(),
    }

    resp = _json_response(response_data)
    resp.set_cookie("va_sid", sid, httponly=True, samesite="lax")
    return resp


def _check_mapping_warnings() -> list[str]:
    import os
    from services.data_helpers import MAPPING_PATH
    warnings = []
    if not os.path.exists(MAPPING_PATH):
        warnings.append("mapping.xlsx not found — output has no Region/Market enrichment.")
    return warnings


# ── GET /api/tab1/download/csv ───────────────────────────────────────────────

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


# ── GET /api/tab1/download/xlsx ──────────────────────────────────────────────

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


# ── Helper ───────────────────────────────────────────────────────────────────

def _load_session_df(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "final_db_bytes")
    if raw is None:
        raise HTTPException(404, "No mapping data in session. Upload a file first.")
    return pd.read_json(io.StringIO(raw), orient="split")


def _json_response(data):
    from fastapi.responses import JSONResponse
    return JSONResponse(content=data)
