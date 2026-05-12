"""
routers/tab2_variance.py  — UPDATED
Changes:
  1. A/B columns renamed to actual scenario labels in all responses
  2. delta renamed to Variance, delta_pct to Variance %
  3. /run returns hierarchical tree structure for pivot table (tree_records)
  4. top5/bot5 now return up to 20 rows so the frontend slider (max=20) works correctly
  5. All existing fixes retained (NaN sanitisation, session fallback, etc.)
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


# ── Safe serialisation helpers ────────────────────────────────────────────

def _safe_val(v):
    """NaN / inf / numpy scalars → JSON-safe Python types."""
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
    """
    iloc-based serialisation — safe for column names with spaces/special chars.
    Never uses itertuples() which mangles column names.
    """
    cols = df.columns.tolist()
    result = []
    for i in range(len(df)):
        row_dict = {}
        for j, col in enumerate(cols):
            row_dict[col] = _safe_val(df.iloc[i, j])
        result.append(row_dict)
    return result


def _sanitise_df(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN/inf in float columns; NaN in object columns → empty string."""
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


def _enrich_filter_opts(opts: dict, df: pd.DataFrame) -> dict:
    """
    Ensure the filter-options dict always contains 'functions' and 'departments'
    keys, pulling distinct values from the corresponding columns if they exist.
    This makes the router self-sufficient even if dh.get_filter_options() predates
    these two columns.
    """
    for key, col in [("functions", "Function"), ("departments", "Department")]:
        if key not in opts:
            if col in df.columns:
                opts[key] = sorted(df[col].dropna().unique().tolist())
            else:
                opts[key] = []
    return opts


# ── Column renaming helpers ───────────────────────────────────────────────

def _rename_cols(df: pd.DataFrame, scenario_a: str, scenario_b: str) -> pd.DataFrame:
    """
    Rename internal column names to user-facing labels:
      A         → <scenario_a>
      B         → <scenario_b>
      delta     → Variance
      delta_pct → Variance %
    """
    rename_map = {
        "A":         scenario_a,
        "B":         scenario_b,
        "delta":     "Variance",
        "delta_pct": "Variance %",
    }
    # Only rename columns that actually exist
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    return df.rename(columns=rename_map)


def _rename_record_keys(record: dict, scenario_a: str, scenario_b: str) -> dict:
    """Rename keys in a single record dict."""
    key_map = {
        "A":         scenario_a,
        "B":         scenario_b,
        "delta":     "Variance",
        "delta_pct": "Variance %",
    }
    return {key_map.get(k, k): v for k, v in record.items()}


# ── Hierarchical tree builder ─────────────────────────────────────────────

def _build_tree(leaf_df: pd.DataFrame, group_fields: list,
                scenario_a: str, scenario_b: str) -> list:
    """
    Build a nested tree from the flat leaf_df for the pivot table.
    Each node has:
      {
        "label":    str,           # dimension value
        "level":    int,           # 0 = top group, len-1 = leaf
        "is_leaf":  bool,
        "<sc_a>":   float,         # sum of A
        "<sc_b>":   float,         # sum of B
        "Variance": float,         # A - B
        "Variance %": float|None,
        "children": [...] | []     # sub-nodes (empty for leaf)
      }
    """
    col_a    = scenario_a   # after rename these are the labels we expose
    col_b    = scenario_b
    col_var  = "Variance"
    col_vpct = "Variance %"

    # Work on internal column names (A, B, delta, delta_pct)
    def _agg_node(sub_df: pd.DataFrame, field_idx: int) -> list:
        if field_idx >= len(group_fields):
            return []

        field  = group_fields[field_idx]
        result = []

        for val, grp in sub_df.groupby(field, dropna=False, sort=False):
            a_sum = float(grp["A"].sum())
            b_sum = float(grp["B"].sum())
            var   = a_sum - b_sum
            vpct  = (var / b_sum * 100) if b_sum != 0 else None

            is_leaf   = (field_idx == len(group_fields) - 1)
            children  = [] if is_leaf else _agg_node(grp, field_idx + 1)

            node = {
                "label":   str(val) if val is not None else "",
                "field":   field,
                "level":   field_idx,
                "is_leaf": is_leaf,
                col_a:     _safe_val(a_sum),
                col_b:     _safe_val(b_sum),
                col_var:   _safe_val(var),
                col_vpct:  _safe_val(vpct),
                "children": children,
            }
            result.append(node)

        return result

    return _agg_node(leaf_df, 0)


# ── POST /api/tab2/upload ─────────────────────────────────────────────────

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
    opts = _enrich_filter_opts(dh.get_filter_options(df), df)
    resp = JSONResponse({
        "session_id": sid,
        "rows":       len(df),
        "columns":    df.columns.tolist(),
        **opts,
    })
    return _set_cookie(resp, sid)


# ── POST /api/tab2/upload-two ─────────────────────────────────────────────

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
    opts = _enrich_filter_opts(dh.get_filter_options(df), df)
    resp = JSONResponse({
        "session_id": sid,
        "rows":       len(df),
        "columns":    df.columns.tolist(),
        **opts,
    })
    return _set_cookie(resp, sid)


# ── GET /api/tab2/filters ─────────────────────────────────────────────────

@router.get("/filters")
async def get_filters(request: Request):
    sid = _sid(request)
    df  = _load_master(sid)
    return JSONResponse(_enrich_filter_opts(dh.get_filter_options(df), df))


# ── POST /api/tab2/load-tab1 ─────────────────────────────────────────────

@router.post("/load-tab1")
async def load_tab1(request: Request):
    sid = _sid(request)
    raw = ss.get(sid, "final_db_bytes")
    if raw is None:
        raise HTTPException(
            404,
            "No Tab 1 mapping data found. "
            "Go to the Tagetik Mapping tab, upload your file and click Generate Mapping first."
        )

    df = pd.read_json(io.StringIO(raw), orient="split")
    _store_master(sid, df)

    opts = _enrich_filter_opts(dh.get_filter_options(df), df)
    resp = JSONResponse({
        "session_id": sid,
        "rows":       len(df),
        "columns":    df.columns.tolist(),
        "source":     "tab1",
        **opts,
    })
    return _set_cookie(resp, sid)


# ── POST /api/tab2/run ────────────────────────────────────────────────────

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
    sel_functions      = body.get("sel_functions", [])
    sel_departments    = body.get("sel_departments", [])
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

    # ── Apply filters (gracefully handles older data_helpers) ────────────
    try:
        df_filtered = dh.apply_filters(
            df, scenario_a, scenario_b,
            sel_markets, sel_regions,
            sel_divisions, sel_entities, sel_lc_oh,
            sel_functions=sel_functions,
            sel_departments=sel_departments,
        )
    except TypeError:
        # data_helpers predates Function/Department params — filter manually
        df_filtered = dh.apply_filters(
            df, scenario_a, scenario_b,
            sel_markets, sel_regions,
            sel_divisions, sel_entities, sel_lc_oh,
        )
        if sel_functions and "Function" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["Function"].isin(sel_functions)]
        if sel_departments and "Department" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["Department"].isin(sel_departments)]

    try:
        leaf_df, pivot_source_long, period_label = dh.run_variance(
            df_filtered, group_fields,
            scenario_a, scenario_b, sel_period, month_cols,
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))

    # ── Build hierarchical tree (uses internal A/B/delta names) ─────────
    tree_records = _build_tree(leaf_df, group_fields, scenario_a, scenario_b)

    # ── Sanitise leaf_df before renaming ────────────────────────────────
    leaf_df = _sanitise_df(leaf_df)

    # ── Rename columns: A→scenario_a, B→scenario_b, delta→Variance ──────
    leaf_df_display = _rename_cols(leaf_df, scenario_a, scenario_b)

    # ── Store in session (keep internal names for Excel export) ──────────
    ss.set(sid, "leaf_df_bytes",   leaf_df.to_json(orient="split"))  # original names
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
        "sel_functions":      sel_functions,
        "sel_departments":    sel_departments,
    })

    total_a   = float(leaf_df["A"].sum())
    total_b   = float(leaf_df["B"].sum())
    total_var = total_a - total_b
    pct_var   = (total_var / total_b * 100) if total_b != 0 else 0.0
    max_var_raw = leaf_df["delta"].abs().max()
    max_var   = 0.0 if (math.isnan(max_var_raw) or math.isinf(max_var_raw)) else float(max_var_raw)

    # ── Top / bottom 20 rows — frontend slider can show 1..20 of these ──
    # favorable_is_lower=True  → low delta = good (favour) → top20 = nsmallest
    # favorable_is_lower=False → high delta = good (favour) → top20 = nlargest
    top20 = leaf_df.nsmallest(20, "delta") if favorable_is_lower else leaf_df.nlargest(20, "delta")
    bot20 = leaf_df.nlargest(20, "delta")  if favorable_is_lower else leaf_df.nsmallest(20, "delta")

    # Rename top20/bot20 for display (A→sc_a, B→sc_b, delta→Variance, delta_pct→Variance %)
    top20_display = _rename_cols(_sanitise_df(top20), scenario_a, scenario_b)
    bot20_display = _rename_cols(_sanitise_df(bot20), scenario_a, scenario_b)

    return JSONResponse({
        "period_label":       period_label,
        "scenario_a":         scenario_a,
        "scenario_b":         scenario_b,
        "col_a":              scenario_a,       # column header for A
        "col_b":              scenario_b,       # column header for B
        "total_a":            dh.fmt_num(total_a),
        "total_b":            dh.fmt_num(total_b),
        "total_variance":     dh.fmt_num(total_var),
        "pct_variance":       f"{pct_var:+.1f}%",
        "max_variance":       dh.fmt_num(max_var),
        "favorable_is_lower": favorable_is_lower,
        "rows":               len(leaf_df),
        # Flat table (renamed columns for display)
        "columns":            leaf_df_display.columns.tolist(),
        "records":            _safe_records(leaf_df_display),
        # Hierarchical tree for pivot UI
        "tree_records":       tree_records,
        "group_fields":       group_fields,
        # top5/bot5 keys kept for backward compatibility — now carry up to 20 rows
        "top5":               _safe_records(top20_display),
        "bot5":               _safe_records(bot20_display),
    })


# ── GET /api/tab2/download/xlsx ───────────────────────────────────────────

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
