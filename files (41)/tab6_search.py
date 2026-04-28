"""
routers/tab6_search.py
───────────────────────
Tab 6 — Commentary Search (FastAPI router)

Endpoints
---------
GET  /api/tab6/filters          Return unique filter values from master DB
POST /api/tab6/search           Return filtered rows as JSON
GET  /api/tab6/download/csv     Download filtered CSV
GET  /api/tab6/download/xlsx    Download filtered Excel
"""

from __future__ import annotations

import io
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


def _load_master() -> pd.DataFrame:
    if not MASTER_XLSX.exists():
        raise HTTPException(404, f"Master database not found at {MASTER_XLSX}. Use the PPT Upload tab first.")
    try:
        df = pd.read_excel(MASTER_XLSX)
        for col in FILTER_COLS:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna("")
        if "Comments" in df.columns:
            df["Comments"] = df["Comments"].astype(str).fillna("")
        return df
    except Exception as exc:
        raise HTTPException(500, f"Error reading master database: {exc}")


# ── GET /api/tab6/filters ────────────────────────────────────────────────────

@router.get("/filters")
async def get_filters():
    df   = _load_master()
    opts = {}
    for col in FILTER_COLS:
        if col in df.columns:
            vals = sorted({v for v in df[col].astype(str).tolist() if v.strip()})
            opts[col] = vals
    return JSONResponse({"filter_cols": FILTER_COLS, "options": opts, "total_rows": len(df)})


# ── POST /api/tab6/search ────────────────────────────────────────────────────

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
            df = df[df[col].astype(str).isin(vals)]

    # Apply text search
    q = (body.get("search_text") or "").strip()
    if q and "Comments" in df.columns:
        df = df[df["Comments"].str.contains(q, case=False, na=False)]

    # Store for download
    ss.set(sid, "search_result_bytes", df.to_json(orient="split"))

    cols = df.columns.tolist()
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    return JSONResponse({"columns": cols, "records": records, "count": len(df)})


# ── GET /api/tab6/download/csv ───────────────────────────────────────────────

@router.get("/download/csv")
async def download_csv(request: Request):
    sid = _sid(request)
    df  = _get_result_df(sid)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(
        iter([buf.getvalue().encode()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Filtered_Commentary.csv"},
    )


# ── GET /api/tab6/download/xlsx ──────────────────────────────────────────────

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


def _get_result_df(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "search_result_bytes")
    if not raw:
        raise HTTPException(404, "No search result in session. Run a search first.")
    return pd.read_json(io.StringIO(raw), orient="split")
