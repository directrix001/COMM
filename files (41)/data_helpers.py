"""
services/data_helpers.py
─────────────────────────
Pure-Python data logic ported from utils/data_helpers.py.
No Streamlit dependency — safe to import from FastAPI routers.
"""

from __future__ import annotations

import io
import os
import re
from typing import List, Tuple

import numpy as np
import pandas as pd

# ── Constants (inline — no utils.constants import needed) ────────────────────
import calendar

FULL_TO_ABBR     = {m: calendar.month_abbr[i] for i, m in enumerate(calendar.month_name) if m}
ABBR_SET         = set(calendar.month_abbr[1:])
MONTH_HEADER_REGEX = r"\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
MONTH_TO_FYNUM   = {
    "Apr":1,"May":2,"Jun":3,"Jul":4,"Aug":5,"Sep":6,
    "Oct":7,"Nov":8,"Dec":9,"Jan":10,"Feb":11,"Mar":12,
}
MAPPING_PATH = os.path.join("backend", "mapping.xlsx")
PREF_GROUP_ORDER = [
    "OH/LC","CostCat description","Division_Desc",
    "Function_Desc","Departement_desc","Entity_desc",
]


# ── Header normalisation ─────────────────────────────────────────────────────

def normalize_month_header(col) -> str:
    if hasattr(col, "strftime"):
        return f"{col.day}-{col.strftime('%b')}"
    s = str(col).strip()
    m = re.match(r"^0?(\d{1,2})\s*[-/ ]\s*([A-Za-z]+)$", s)
    if m:
        d, mon_txt = int(m.group(1)), m.group(2).capitalize()
        if mon_txt in FULL_TO_ABBR:
            return f"{d}-{FULL_TO_ABBR[mon_txt]}"
        if len(mon_txt) == 3 and mon_txt.title() in ABBR_SET:
            return f"{d}-{mon_txt.title()}"
    m = re.match(r"^0?(\d{1,2})\s*[-/ ]\s*([A-Za-z]{3})$", s)
    if m:
        return f"{int(m.group(1))}-{m.group(2).title()}"
    m = re.match(
        r"^0?(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$",
        s, re.IGNORECASE,
    )
    if m:
        return f"{int(m.group(1))}-{m.group(2).title()}"
    return s


def normalize_df_headers(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2.columns = [normalize_month_header(c) for c in df.columns]
    return df2


def get_month_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if re.fullmatch(MONTH_HEADER_REGEX, str(c))]


def clean_numeric_series(s: pd.Series) -> pd.Series:
    s2 = s.astype(str).str.strip()
    s2 = s2.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s2 = s2.str.replace(",", "", regex=False)
    return pd.to_numeric(s2, errors="coerce").fillna(0.0)


# ── Read & normalise ─────────────────────────────────────────────────────────

def read_and_normalise(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    return normalize_df_headers(raw)


def generate_mapping(file_bytes: bytes) -> pd.DataFrame:
    """Full Tab-1 mapping pipeline."""
    df = read_and_normalise(file_bytes)
    month_cols = get_month_cols(df)
    if not month_cols:
        raise ValueError("No month columns found (expected '1-Apr' format).")

    df2, _, _ = compute_mtd_ytd(df, 1)

    mapping_df = None
    if os.path.exists(MAPPING_PATH):
        try:
            mapping_df = pd.read_excel(MAPPING_PATH, engine="openpyxl")
        except Exception:
            pass

    if mapping_df is not None:
        req1 = {"Entity_desc","Region","Entity","Market"}
        req2 = {"CostCat description","OH/LC"}
        if req1.issubset(mapping_df.columns) and req2.issubset(mapping_df.columns):
            df_final = df2.merge(
                mapping_df[["Entity_desc","Region","Entity","Market"]],
                on="Entity_desc", how="left",
            ).merge(
                mapping_df[["CostCat description","OH/LC"]],
                on="CostCat description", how="left",
            )
        else:
            df_final = df2.copy()
    else:
        df_final = df2.copy()

    return df_final


def compute_mtd_ytd(df: pd.DataFrame, fy_index: int) -> Tuple[pd.DataFrame, List[str], str]:
    month_cols = get_month_cols(df)
    if not month_cols:
        raise ValueError("No month columns found.")
    df_month_numeric = df[month_cols].apply(pd.to_numeric, errors="coerce")
    df = df.copy()
    df["YTD"] = df_month_numeric.sum(axis=1)
    num_to_col = {}
    for c in month_cols:
        parts = str(c).split("-")
        if len(parts) < 2:
            continue
        mon = parts[1].title()
        if mon in MONTH_TO_FYNUM:
            num_to_col[MONTH_TO_FYNUM[mon]] = c
    if fy_index not in num_to_col:
        raise ValueError(f"FY month {fy_index} not in data. Found: {sorted(num_to_col.keys())}")
    target_col = num_to_col[fy_index]
    df["MTD"] = pd.to_numeric(df[target_col], errors="coerce")
    return df, month_cols, target_col


# ── Filter helpers ───────────────────────────────────────────────────────────

def get_filter_options(df: pd.DataFrame) -> dict:
    def _u(col):
        return sorted(df[col].astype(str).dropna().unique().tolist()) if col in df.columns else []
    return {
        "scenarios": _u("Scenario"),
        "markets":   _u("Market"),
        "regions":   _u("Region"),
        "divisions": _u("Division_Desc"),
        "entities":  _u("Entity_desc") if "Entity_desc" in df.columns else _u("Entity"),
        "lc_oh":     _u("OH/LC"),
        "month_cols": get_month_cols(df),
        "avail_group": [k for k in PREF_GROUP_ORDER if k in df.columns],
    }


def apply_filters(
    df: pd.DataFrame,
    scenario_a: str, scenario_b: str,
    sel_markets: list, sel_regions: list,
    sel_divisions: list, sel_entities: list,
    sel_lc_oh: list,
) -> pd.DataFrame:
    df_work = df.copy()
    df_work["Scenario"] = df_work["Scenario"].astype(str).str.strip()
    if sel_markets   and "Market"       in df_work.columns:
        df_work = df_work[df_work["Market"].astype(str).isin(sel_markets)]
    if sel_regions   and "Region"       in df_work.columns:
        df_work = df_work[df_work["Region"].astype(str).isin(sel_regions)]
    if sel_divisions and "Division_Desc" in df_work.columns:
        df_work = df_work[df_work["Division_Desc"].astype(str).isin(sel_divisions)]
    if sel_entities  and "Entity_desc"  in df_work.columns:
        df_work = df_work[df_work["Entity_desc"].astype(str).isin(sel_entities)]
    elif sel_entities and "Entity"      in df_work.columns:
        df_work = df_work[df_work["Entity"].astype(str).isin(sel_entities)]
    if sel_lc_oh     and "OH/LC"        in df_work.columns:
        df_work = df_work[df_work["OH/LC"].astype(str).isin(sel_lc_oh)]
    return df_work[df_work["Scenario"].isin([scenario_a, scenario_b])]


def run_variance(
    df_filtered: pd.DataFrame,
    group_fields: list,
    scenario_a: str, scenario_b: str,
    sel_period: str,
    month_cols_avail: list,
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    df_work = df_filtered.copy()

    if sel_period == "__YTD_CALC__":
        mc = [c for c in month_cols_avail if c in df_work.columns]
        df_work["__VALUE__"] = df_work[mc].apply(lambda r: clean_numeric_series(r).sum(), axis=1)
        value_col, period_label = "__VALUE__", "YTD (computed)"
    else:
        value_col, period_label = sel_period, sel_period

    base = df_work[group_fields + ["Scenario", value_col]].rename(columns={value_col: "Value"}).copy()
    base["Value"] = clean_numeric_series(base["Value"])

    agg  = base.groupby(group_fields + ["Scenario"], dropna=False)["Value"].sum().reset_index()
    pivot_source_long = agg.copy()

    piv = agg.pivot_table(
        index=group_fields, columns="Scenario", values="Value",
        aggfunc="sum", fill_value=0.0,
    )
    for s in [scenario_a, scenario_b]:
        if s not in piv.columns:
            piv[s] = 0.0
    piv = piv[[scenario_a, scenario_b]].rename(columns={scenario_a: "A", scenario_b: "B"})

    leaf_df = piv.reset_index()
    leaf_df["delta"]   = leaf_df["A"] - leaf_df["B"]
    leaf_df["delta_pct"] = np.where(leaf_df["B"] == 0, None, (leaf_df["delta"] / leaf_df["B"]) * 100)

    return leaf_df, pivot_source_long, period_label


# ── Formatting ───────────────────────────────────────────────────────────────

def fmt_num(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:,.2f}M"
        if abs(v) >= 1_000:
            return f"{v/1_000:,.1f}K"
        return f"{v:,.0f}"
    except Exception:
        return str(v)


def df_to_records(df: pd.DataFrame) -> list:
    """Convert DataFrame to JSON-safe list of dicts (NaN → None)."""
    return df.where(pd.notnull(df), None).to_dict(orient="records")
