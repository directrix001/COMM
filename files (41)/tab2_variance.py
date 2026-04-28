"""
routers/tab2_variance.py
─────────────────────────
Tab 2 — Variance Analysis  (FastAPI router)

Endpoints
---------
POST /api/tab2/upload          Upload master DB (single file)
POST /api/tab2/upload-two      Upload two files (A + B scenarios)
GET  /api/tab2/filters         Return filter options for loaded data
POST /api/tab2/run             Run variance pivot with chosen filters
GET  /api/tab2/download/xlsx   Download variance Excel report
"""

from __future__ import annotations

import io
import uuid

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from services import data_helpers as dh
from services import session_store as ss
from services.excel_export import build_excel_export

router = APIRouter()


def _sid(request: Request) -> str:
    return request.cookies.get("va_sid", str(uuid.uuid4()))


def _store_master(sid: str, df: pd.DataFrame) -> None:
    ss.set(sid, "master_db_bytes", df.to_json(orient="split"))


def _load_master(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "master_db_bytes")
    if raw is None:
        raise HTTPException(404, "No master data in session. Upload a file first.")
    return pd.read_json(io.StringIO(raw), orient="split")


def _set_cookie(resp, sid: str):
    resp.set_cookie("va_sid", sid, httponly=True, samesite="lax")
    return resp


# ── POST /api/tab2/upload ────────────────────────────────────────────────────

@router.post("/upload")
async def upload_master(request: Request, file: UploadFile = File(...)):
    """Upload a single Master DB file that already has a Scenario column."""
    sid = _sid(request)
    file_bytes = await file.read()
    try:
        df = dh.read_and_normalise(file_bytes)
    except Exception as exc:
        raise HTTPException(422, str(exc))

    if "Scenario" not in df.columns:
        raise HTTPException(422, "File must contain a 'Scenario' column.")

    _store_master(sid, df)
    opts = dh.get_filter_options(df)
    resp = JSONResponse({"session_id": sid, "rows": len(df), "columns": df.columns.tolist(), **opts})
    return _set_cookie(resp, sid)


# ── POST /api/tab2/upload-two ────────────────────────────────────────────────

@router.post("/upload-two")
async def upload_two(
    request: Request,
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    label_a: str = Form("Scenario_A"),
    label_b: str = Form("Scenario_B"),
):
    """Upload two separate files and merge them with assigned scenario labels."""
    sid = _sid(request)
    try:
        dfa = dh.read_and_normalise(await file_a.read()).copy()
        dfb = dh.read_and_normalise(await file_b.read()).copy()
    except Exception as exc:
        raise HTTPException(422, str(exc))

    dfa["Scenario"] = label_a.strip() or "Scenario_A"
    dfb["Scenario"] = label_b.strip() or "Scenario_B"
    common = list(set(dfa.columns) & set(dfb.columns))
    df = pd.concat([dfa[common], dfb[common]], ignore_index=True)

    _store_master(sid, df)
    opts = dh.get_filter_options(df)
    resp = JSONResponse({"session_id": sid, "rows": len(df), "columns": df.columns.tolist(), **opts})
    return _set_cookie(resp, sid)


# ── GET /api/tab2/filters ────────────────────────────────────────────────────

@router.get("/filters")
async def get_filters(request: Request):
    """Return available filter options for the currently loaded master data."""
    sid = _sid(request)
    df  = _load_master(sid)
    return JSONResponse(dh.get_filter_options(df))


# ── POST /api/tab2/run ───────────────────────────────────────────────────────

@router.post("/run")
async def run_variance(request: Request):
    """
    Body JSON:
    {
      "scenario_a": "Budget",
      "scenario_b": "Actual",
      "sel_period": "3-Jun" | "YTD" | "__YTD_CALC__",
      "group_fields": ["OH/LC", "Division_Desc"],
      "favorable_is_lower": true,
      "sel_markets": [], "sel_regions": [], "sel_divisions": [],
      "sel_entities": [], "sel_lc_oh": []
    }
    """
    sid  = _sid(request)
    df   = _load_master(sid)
    body = await request.json()

    scenario_a       = body.get("scenario_a", "")
    scenario_b       = body.get("scenario_b", "")
    sel_period       = body.get("sel_period", "")
    group_fields     = body.get("group_fields", [])
    favorable_is_lower = body.get("favorable_is_lower", True)
    sel_markets      = body.get("sel_markets", [])
    sel_regions      = body.get("sel_regions", [])
    sel_divisions    = body.get("sel_divisions", [])
    sel_entities     = body.get("sel_entities", [])
    sel_lc_oh        = body.get("sel_lc_oh", [])

    if not group_fields:
        raise HTTPException(422, "group_fields must not be empty.")
    if not scenario_a or not scenario_b:
        raise HTTPException(422, "scenario_a and scenario_b are required.")

    month_cols = dh.get_month_cols(df)
    if sel_period != "__YTD_CALC__" and sel_period not in df.columns and sel_period != "YTD":
        raise HTTPException(422, f"Period column '{sel_period}' not found in data.")

    try:
        df_filtered = dh.apply_filters(
            df, scenario_a, scenario_b,
            sel_markets, sel_regions,
            sel_divisions, sel_entities, sel_lc_oh,
        )
        leaf_df, pivot_source_long, period_label = dh.run_variance(
            df_filtered, group_fields, scenario_a, scenario_b, sel_period, month_cols
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))

    # Store result in session for download
    ss.set(sid, "leaf_df_bytes",     leaf_df.to_json(orient="split"))
    ss.set(sid, "pivot_src_bytes",   pivot_source_long.to_json(orient="split"))
    ss.set(sid, "var_context",       {
        "sel_period": period_label, "scenario_a": scenario_a, "scenario_b": scenario_b,
        "header_a": f"{scenario_a} (A)", "header_b": f"{scenario_b} (B)",
        "group_fields": group_fields, "favorable_is_lower": favorable_is_lower,
        "sel_markets": sel_markets, "sel_regions": sel_regions,
        "sel_divisions": sel_divisions,
    })

    total_a   = float(leaf_df["A"].sum())
    total_b   = float(leaf_df["B"].sum())
    total_var = total_a - total_b
    pct_var   = (total_var / total_b * 100) if total_b != 0 else 0.0
    max_var   = float(leaf_df["delta"].abs().max())

    # Top/Bottom 5
    top5  = leaf_df.nsmallest(5, "delta") if favorable_is_lower else leaf_df.nlargest(5, "delta")
    bot5  = leaf_df.nlargest(5, "delta")  if favorable_is_lower else leaf_df.nsmallest(5, "delta")

    return JSONResponse({
        "period_label":   period_label,
        "total_a":        dh.fmt_num(total_a),
        "total_b":        dh.fmt_num(total_b),
        "total_variance": dh.fmt_num(total_var),
        "pct_variance":   f"{pct_var:+.1f}%",
        "max_variance":   dh.fmt_num(max_var),
        "favorable_is_lower": favorable_is_lower,
        "rows":           len(leaf_df),
        "columns":        leaf_df.columns.tolist(),
        "records":        _safe_records(leaf_df),
        "top5":           _safe_records(top5),
        "bot5":           _safe_records(bot5),
        "hotspot":        _build_hotspot(leaf_df, group_fields, favorable_is_lower),
    })


# ── GET /api/tab2/download/xlsx ──────────────────────────────────────────────

@router.get("/download/xlsx")
async def download_xlsx(request: Request):
    sid = _sid(request)
    raw_leaf = ss.get(sid, "leaf_df_bytes")
    raw_src  = ss.get(sid, "pivot_src_bytes")
    ctx      = ss.get(sid, "var_context")

    if not raw_leaf or not ctx:
        raise HTTPException(404, "No variance result in session. Run analysis first.")

    leaf_df           = pd.read_json(io.StringIO(raw_leaf), orient="split")
    pivot_source_long = pd.read_json(io.StringIO(raw_src),  orient="split") if raw_src else None

    excel_bytes = build_excel_export(
        leaf_df=leaf_df,
        group_fields=ctx["group_fields"],
        header_a=ctx["header_a"],
        header_b=ctx["header_b"],
        sel_period=ctx["sel_period"],
        sel_markets=ctx.get("sel_markets", []),
        sel_regions=ctx.get("sel_regions", []),
        sel_divisions=ctx.get("sel_divisions", []),
        scenario_a=ctx["scenario_a"],
        scenario_b=ctx["scenario_b"],
        favorable_is_lower=ctx["favorable_is_lower"],
        pivot_source_long=pivot_source_long,
    )

    safe_period = ctx["sel_period"].replace("/", "-")
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=variance_report_{safe_period}.xlsx"},
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_records(df: pd.DataFrame) -> list:
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def _build_hotspot(leaf_df: pd.DataFrame, group_fields: list, fav_lower: bool) -> list:
    if not group_fields or leaf_df.empty:
        return []
    last_dim = group_fields[-1]
    if last_dim not in leaf_df.columns:
        return []
    agg = (
        leaf_df.groupby(last_dim, dropna=False)
        .agg(A=("A","sum"), B=("B","sum"))
        .reset_index()
    )
    agg["delta"] = agg["A"] - agg["B"]
    agg["pct"]   = np.where(agg["B"] == 0, None, (agg["delta"] / agg["B"]) * 100)
    sorted_agg   = (
        agg.sort_values("delta", ascending=False)
        if fav_lower else
        agg.sort_values("delta", ascending=True)
    ).head(4)
    return _safe_records(sorted_agg)
