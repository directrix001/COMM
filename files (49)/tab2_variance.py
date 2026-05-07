"""
routers/tab2_variance.py  — v3
Changes vs previous:
  1. delta → "Variance (M€)"   — divided by 1,000,000 → 2 decimal float
  2. delta_pct → "Variance %"  — multiplied by 100, rounded to 2 decimal float
  3. A → scenario_a label, B → scenario_b label in returned records
  4. scenario_a / scenario_b labels sent back so JS can rename table headers
  5. hotspot removed from response (UI change handled in tab2.js)
  6. All existing NaN / iloc / session-fallback fixes retained
"""
from __future__ import annotations

import io
import math
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


# ── Safe serialisation ────────────────────────────────────────────────────

def _safe_val(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    try:
        import numpy as np
        if isinstance(v, (np.floating,)):
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, np.bool_):
            return bool(v)
    except ImportError:
        pass
    return v


def _safe_records(df: pd.DataFrame) -> list:
    """iloc-based — safe for column names with spaces or special chars."""
    cols = df.columns.tolist()
    result = []
    for i in range(len(df)):
        row_dict = {}
        for j, col in enumerate(cols):
            row_dict[col] = _safe_val(df.iloc[i, j])
        result.append(row_dict)
    return result


def _sanitise_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include=["float", "float64", "float32"]).columns:
        df[col] = df[col].apply(
            lambda x: None if (x is None or (isinstance(x, float)
                               and (math.isnan(x) or math.isinf(x)))) else x
        )
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: "" if (x is None or (isinstance(x, float)
                             and math.isnan(x))) else x
        )
    return df


# ── Session helpers ───────────────────────────────────────────────────────

def _store_master(sid: str, df: pd.DataFrame) -> None:
    ss.set(sid, "master_db_bytes", df.to_json(orient="split"))


def _load_master(sid: str) -> pd.DataFrame:
    raw = ss.get(sid, "master_db_bytes")
    if raw is None:
        raw = ss.get(sid, "final_db_bytes")
    if raw is None:
        raise HTTPException(
            404,
            "No data in session. "
            "Either run Tagetik Mapping (Tab 1) first, or upload a file here."
        )
    return pd.read_json(io.StringIO(raw), orient="split")


def _set_cookie(resp, sid: str):
    resp.set_cookie("va_sid", sid, httponly=True, samesite="lax")
    return resp


# ── Column rename + millions conversion ──────────────────────────────────

def _format_leaf_df(df: pd.DataFrame, scenario_a: str, scenario_b: str) -> pd.DataFrame:
    """
    Rename internal column names to display-friendly labels:
      A          → <scenario_a>
      B          → <scenario_b>
      delta      → Variance (M€)   [divided by 1,000,000, 2dp]
      delta_pct  → Variance %      [×100, 2dp float]
    """
    df = df.copy()

    # Convert raw numbers → millions (2 decimal places)
    if "A" in df.columns:
        df["A"] = (df["A"] / 1_000_000).round(2)
    if "B" in df.columns:
        df["B"] = (df["B"] / 1_000_000).round(2)
    if "delta" in df.columns:
        df["delta"] = (df["delta"] / 1_000_000).round(2)
    if "delta_pct" in df.columns:
        # delta_pct from data_helpers is already a ratio (0.02 = 2%)
        # Convert to percentage float rounded to 2dp: 0.021234 → 2.12
        df["delta_pct"] = (df["delta_pct"] * 100).round(2)

    # Rename columns
    rename_map = {
        "A":         scenario_a,
        "B":         scenario_b,
        "delta":     "Variance (M€)",
        "delta_pct": "Variance %",
    }
    df = df.rename(columns=rename_map)
    return df


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_master(request: Request, file: UploadFile = File(...)):
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
    resp = JSONResponse({"session_id": sid, "rows": len(df),
                         "columns": df.columns.tolist(), **opts})
    return _set_cookie(resp, sid)


@router.post("/upload-two")
async def upload_two(
    request: Request,
    file_a:  UploadFile = File(...),
    file_b:  UploadFile = File(...),
    label_a: str = Form("Scenario_A"),
    label_b: str = Form("Scenario_B"),
):
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
    resp = JSONResponse({"session_id": sid, "rows": len(df),
                         "columns": df.columns.tolist(), **opts})
    return _set_cookie(resp, sid)


@router.get("/filters")
async def get_filters(request: Request):
    sid = _sid(request)
    df  = _load_master(sid)
    return JSONResponse(dh.get_filter_options(df))


@router.post("/load-tab1")
async def load_tab1(request: Request):
    sid = _sid(request)
    raw = ss.get(sid, "final_db_bytes")
    if raw is None:
        raise HTTPException(
            404,
            "No Tab 1 mapping data found. "
            "Go to Tagetik Mapping tab, upload your file and click Generate Mapping first."
        )
    df = pd.read_json(io.StringIO(raw), orient="split")
    _store_master(sid, df)
    opts = dh.get_filter_options(df)
    resp = JSONResponse({"session_id": sid, "rows": len(df),
                         "columns": df.columns.tolist(), "source": "tab1", **opts})
    return _set_cookie(resp, sid)


@router.post("/run")
async def run_variance(request: Request):
    sid  = _sid(request)
    df   = _load_master(sid)
    body = await request.json()

    scenario_a         = body.get("scenario_a", "")
    scenario_b         = body.get("scenario_b", "")
    sel_period         = body.get("sel_period", "")
    group_fields       = body.get("group_fields", [])
    favorable_is_lower = body.get("favorable_is_lower", True)
    sel_markets        = body.get("sel_markets", [])
    sel_regions        = body.get("sel_regions", [])
    sel_divisions      = body.get("sel_divisions", [])
    sel_entities       = body.get("sel_entities", [])
    sel_lc_oh          = body.get("sel_lc_oh", [])

    if not group_fields:
        raise HTTPException(422, "group_fields must not be empty.")
    if not scenario_a or not scenario_b:
        raise HTTPException(422, "scenario_a and scenario_b are required.")

    month_cols = dh.get_month_cols(df)
    if (sel_period != "__YTD_CALC__"
            and sel_period not in df.columns
            and sel_period != "YTD"):
        raise HTTPException(422, f"Period column '{sel_period}' not found in data.")

    try:
        df_filtered = dh.apply_filters(
            df, scenario_a, scenario_b,
            sel_markets, sel_regions, sel_divisions, sel_entities, sel_lc_oh,
        )
        leaf_df, pivot_source_long, period_label = dh.run_variance(
            df_filtered, group_fields,
            scenario_a, scenario_b, sel_period, month_cols,
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))

    # Sanitise raw leaf_df (still has A/B/delta/delta_pct)
    leaf_df = _sanitise_df(leaf_df)

    # Store raw (millions-converted) for Excel download
    ss.set(sid, "leaf_df_bytes",   leaf_df.to_json(orient="split"))
    ss.set(sid, "pivot_src_bytes", pivot_source_long.to_json(orient="split"))
    ss.set(sid, "var_context", {
        "sel_period":         period_label,
        "scenario_a":         scenario_a,
        "scenario_b":         scenario_b,
        "header_a":           f"{scenario_a} (A)",
        "header_b":           f"{scenario_b} (B)",
        "group_fields":       group_fields,
        "favorable_is_lower": favorable_is_lower,
        "sel_markets":        sel_markets,
        "sel_regions":        sel_regions,
        "sel_divisions":      sel_divisions,
    })

    # KPI totals (raw, before millions conversion)
    total_a   = float(leaf_df["A"].sum())
    total_b   = float(leaf_df["B"].sum())
    total_var = total_a - total_b
    pct_var   = (total_var / total_b * 100) if total_b != 0 else 0.0
    max_var_r = leaf_df["delta"].abs().max()
    max_var   = 0.0 if (math.isnan(max_var_r) or math.isinf(max_var_r)) else float(max_var_r)

    # Apply display formatting (rename + millions)
    display_df = _format_leaf_df(leaf_df, scenario_a, scenario_b)
    display_df = _sanitise_df(display_df)

    # Column names after rename for JS to use
    col_scenario_a  = scenario_a
    col_scenario_b  = scenario_b
    col_variance_m  = "Variance (M€)"
    col_variance_pct= "Variance %"

    # Top / Bottom 5 (use raw delta for sorting, display formatted)
    top5_raw = leaf_df.nsmallest(5, "delta") if favorable_is_lower else leaf_df.nlargest(5, "delta")
    bot5_raw = leaf_df.nlargest(5, "delta")  if favorable_is_lower else leaf_df.nsmallest(5, "delta")
    top5_disp = _format_leaf_df(_sanitise_df(top5_raw.reset_index(drop=True)), scenario_a, scenario_b)
    bot5_disp = _format_leaf_df(_sanitise_df(bot5_raw.reset_index(drop=True)), scenario_a, scenario_b)

    return JSONResponse({
        "period_label":       period_label,
        "scenario_a":         scenario_a,
        "scenario_b":         scenario_b,
        "col_variance_m":     col_variance_m,
        "col_variance_pct":   col_variance_pct,
        "total_a":            f"{total_a/1_000_000:.2f}M",
        "total_b":            f"{total_b/1_000_000:.2f}M",
        "total_variance":     f"{total_var/1_000_000:.2f}M",
        "pct_variance":       f"{pct_var:+.2f}%",
        "max_variance":       f"{max_var/1_000_000:.2f}M",
        "favorable_is_lower": favorable_is_lower,
        "rows":               len(display_df),
        "group_fields":       group_fields,
        "columns":            display_df.columns.tolist(),
        "records":            _safe_records(display_df),
        "top5":               _safe_records(top5_disp),
        "bot5":               _safe_records(bot5_disp),
        # hotspot intentionally omitted — removed from UI per requirement
    })


@router.get("/download/xlsx")
async def download_xlsx(request: Request):
    sid      = _sid(request)
    raw_leaf = ss.get(sid, "leaf_df_bytes")
    raw_src  = ss.get(sid, "pivot_src_bytes")
    ctx      = ss.get(sid, "var_context")
    if not raw_leaf or not ctx:
        raise HTTPException(404, "No variance result in session. Run analysis first.")
    leaf_df           = pd.read_json(io.StringIO(raw_leaf), orient="split")
    pivot_source_long = pd.read_json(io.StringIO(raw_src), orient="split") if raw_src else None
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
