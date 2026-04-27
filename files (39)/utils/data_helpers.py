"""
utils/data_helpers.py
─────────────────────
Data loading, header normalisation, MTD/YTD computation,
filter-option extraction, filter application, and variance
pivot logic — all cache-decorated so Streamlit never
repeats heavy work unnecessarily.
"""

from __future__ import annotations

import io
import os
import re
from typing import List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from utils.constants import (
    ABBR_SET,
    FULL_TO_ABBR,
    MAPPING_PATH,
    MONTH_HEADER_REGEX,
    MONTH_TO_FYNUM,
)


# ─── Header normalisation ────────────────────────────────────────────────────

def normalize_month_header(col) -> str:
    if hasattr(col, "strftime"):
        return f"{col.day}-{col.strftime('%b')}"
    s = str(col).strip()
    m = re.match(r"^0?(\d{1,2})\s*[-/ ]\s*([A-Za-z]+)$", s)
    if m:
        d = int(m.group(1))
        mon_txt = m.group(2).capitalize()
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


# ─── Cached I/O ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def cached_read_and_normalise(file_bytes: bytes) -> pd.DataFrame:
    """Read raw Excel bytes and normalise month-column headers."""
    raw = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    return normalize_df_headers(raw)


@st.cache_data(show_spinner=False)
def cached_generate_mapping(file_bytes: bytes, mapping_mtime: float) -> pd.DataFrame:
    """
    Run the full Tab-1 mapping pipeline (MTD/YTD + mapping merge).
    `mapping_mtime` is passed solely to bust the cache when mapping.xlsx changes.
    """
    df = cached_read_and_normalise(file_bytes)
    month_cols = get_month_cols(df)
    if not month_cols:
        raise ValueError("No month columns found (expected '1-Apr' format).")

    fy_index = 1
    df2, _, _ = compute_mtd_ytd(df, fy_index)

    mapping_df = None
    if os.path.exists(MAPPING_PATH):
        try:
            mapping_df = pd.read_excel(MAPPING_PATH, engine="openpyxl")
        except Exception:
            pass

    if mapping_df is not None:
        req1 = {"Entity_desc", "Region", "Entity", "Market"}
        req2 = {"CostCat description", "OH/LC"}
        if req1.issubset(mapping_df.columns) and req2.issubset(mapping_df.columns):
            df_final = df2.merge(
                mapping_df[["Entity_desc", "Region", "Entity", "Market"]],
                on="Entity_desc", how="left",
            ).merge(
                mapping_df[["CostCat description", "OH/LC"]],
                on="CostCat description", how="left",
            )
        else:
            df_final = df2.copy()
    else:
        df_final = df2.copy()

    return df_final


def compute_mtd_ytd(
    df: pd.DataFrame, fy_index: int
) -> Tuple[pd.DataFrame, List[str], str]:
    month_cols = get_month_cols(df)
    if not month_cols:
        raise ValueError("No month columns found (expected '1-Apr' format).")
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
        raise ValueError(
            f"FY month {fy_index} not present. Found: {sorted(num_to_col.keys())}"
        )
    target_col = num_to_col[fy_index]
    df["MTD"] = pd.to_numeric(df[target_col], errors="coerce")
    return df, month_cols, target_col


# ─── Filter-option extraction ────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_filter_options(df: pd.DataFrame):
    """Extract all dropdown option lists from master_df once and cache."""
    def _sorted_unique(col):
        return sorted(df[col].astype(str).dropna().unique().tolist()) if col in df.columns else []

    scenarios = _sorted_unique("Scenario")
    markets   = _sorted_unique("Market")
    regions   = _sorted_unique("Region")
    divisions = _sorted_unique("Division_Desc")
    entities  = _sorted_unique("Entity_desc") if "Entity_desc" in df.columns else _sorted_unique("Entity")
    lc_oh     = _sorted_unique("OH/LC")
    month_cols = get_month_cols(df)
    return scenarios, markets, regions, divisions, entities, lc_oh, month_cols


# ─── Filter application ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def cached_apply_filters(
    df: pd.DataFrame,
    scenario_a: str,
    scenario_b: str,
    sel_markets: tuple,
    sel_regions: tuple,
    sel_divisions: tuple,
    sel_entities: tuple,
    sel_lc_oh: tuple,
) -> pd.DataFrame:
    df_work = df.copy()
    df_work["Scenario"] = df_work["Scenario"].astype(str).str.strip()

    if sel_markets and "Market" in df_work.columns:
        df_work = df_work[df_work["Market"].astype(str).isin(sel_markets)]
    if sel_regions and "Region" in df_work.columns:
        df_work = df_work[df_work["Region"].astype(str).isin(sel_regions)]
    if sel_divisions and "Division_Desc" in df_work.columns:
        df_work = df_work[df_work["Division_Desc"].astype(str).isin(sel_divisions)]
    if sel_entities and "Entity_desc" in df_work.columns:
        df_work = df_work[df_work["Entity_desc"].astype(str).isin(sel_entities)]
    elif sel_entities and "Entity" in df_work.columns:
        df_work = df_work[df_work["Entity"].astype(str).isin(sel_entities)]
    if sel_lc_oh and "OH/LC" in df_work.columns:
        df_work = df_work[df_work["OH/LC"].astype(str).isin(sel_lc_oh)]

    return df_work[df_work["Scenario"].isin([scenario_a, scenario_b])]


# ─── Variance pivot ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def cached_run_variance(
    df_filtered: pd.DataFrame,
    group_fields: tuple,
    scenario_a: str,
    scenario_b: str,
    sel_period: str,
    month_cols_avail: tuple,
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Aggregate, pivot and compute variance columns.

    Returns
    -------
    leaf_df            – pivoted frame with A, B, Δ, Δ% columns
    pivot_source_long  – long-form aggregation (for PivotSource sheet)
    period_label       – human-readable period string
    """
    df_work = df_filtered.copy()
    gf_list = list(group_fields)
    mc_list = list(month_cols_avail)

    if sel_period == "__YTD_CALC__":
        mc_avail_work = [c for c in mc_list if c in df_work.columns]
        df_work["__VALUE__"] = df_work[mc_avail_work].apply(
            lambda r: clean_numeric_series(r).sum(), axis=1
        )
        value_col    = "__VALUE__"
        period_label = "YTD (computed)"
    else:
        value_col    = sel_period
        period_label = sel_period

    use_cols = gf_list + ["Scenario", value_col]
    base = df_work[use_cols].rename(columns={value_col: "Value"}).copy()
    base["Value"] = clean_numeric_series(base["Value"])

    agg = base.groupby(gf_list + ["Scenario"], dropna=False)["Value"].sum().reset_index()
    pivot_source_long = agg.copy()

    piv = agg.pivot_table(
        index=gf_list, columns="Scenario", values="Value",
        aggfunc="sum", fill_value=0.0,
    )
    for s in [scenario_a, scenario_b]:
        if s not in piv.columns:
            piv[s] = 0.0
    piv = piv[[scenario_a, scenario_b]].rename(
        columns={scenario_a: "A", scenario_b: "B"}
    )

    leaf_df = piv.reset_index()
    leaf_df["Δ (A-B)"] = leaf_df["A"] - leaf_df["B"]
    leaf_df["Δ% vs B"] = np.where(
        leaf_df["B"] == 0, np.nan, leaf_df["Δ (A-B)"] / leaf_df["B"]
    )

    return leaf_df, pivot_source_long, period_label
