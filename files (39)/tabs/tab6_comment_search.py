"""
tabs/tab6_comment_search.py
────────────────────────────
Tab 6 — Commentary Search Engine

Loads the master commentary database (database/Segregateddata.xlsx),
provides multi-select column filters + free-text search over the
Comments column, and lets the user download the filtered result.

Public API
----------
render()   — call inside  `with tab:` in app.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Constants ────────────────────────────────────────────────────────────────

FILTER_COLS = [
    "Category", "Scenarios", "Functions", "Functions-View",
    "Year", "Month", "Region", "Criteria",
]

MASTER_XLSX_PATH = Path("database") / "Segregateddata.xlsx"


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_master(mtime: float) -> pd.DataFrame:
    """Read master DB; keyed on file mtime so edits auto-bust the cache."""
    df = pd.read_excel(MASTER_XLSX_PATH)
    for col in FILTER_COLS:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("")
    if "Comments" in df.columns:
        df["Comments"] = df["Comments"].astype(str).fillna("")
    return df


def _get_master_df() -> pd.DataFrame | None:
    """Return master df from cache or session_state; None on error."""
    if not MASTER_XLSX_PATH.exists():
        st.error(
            f"Master database not found at `{MASTER_XLSX_PATH}`.  \n"
            "Use the **PPT Upload** tab to push data first, or place "
            "`Segregateddata.xlsx` inside the `database/` folder."
        )
        return None
    try:
        mtime = MASTER_XLSX_PATH.stat().st_mtime
        return _load_master(mtime)
    except Exception as exc:
        st.error(f"Error loading master database: {exc}")
        return None


def _apply_filters(
    df: pd.DataFrame,
    selections: dict[str, list[str]],
    search_text: str,
) -> pd.DataFrame:
    filtered = df.copy()
    for col, chosen in selections.items():
        if chosen and col in filtered.columns:
            filtered = filtered[filtered[col].astype(str).isin(chosen)]
    if search_text and "Comments" in filtered.columns:
        filtered = filtered[
            filtered["Comments"].str.contains(search_text, case=False, na=False)
        ]
    return filtered


# ── Main render ──────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown(
        '<p class="va-section-label">🔍 Commentary Search Engine</p>',
        unsafe_allow_html=True,
    )

    df = _get_master_df()
    if df is None:
        return

    # ── Search bar ───────────────────────────────────────────────────────────
    search_col, reset_col = st.columns([5, 1])
    with search_col:
        search_text = st.text_input(
            "Search Comments",
            placeholder="Type keywords to search inside Comments…",
            key="cs_search",
            label_visibility="collapsed",
        )
    with reset_col:
        if st.button("↺ Reset", key="cs_reset"):
            # Clear all widget state for this tab
            for k in list(st.session_state.keys()):
                if k.startswith("cs_"):
                    del st.session_state[k]
            st.rerun()

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    # ── Multi-select filters (2 rows × 4 cols) ───────────────────────────────
    st.markdown('<p class="va-section-label">🎛️ Filters</p>', unsafe_allow_html=True)

    selections: dict[str, list[str]] = {}
    cols_per_row = 4
    available_filter_cols = [c for c in FILTER_COLS if c in df.columns]

    rows = [
        available_filter_cols[i : i + cols_per_row]
        for i in range(0, len(available_filter_cols), cols_per_row)
    ]

    for row_cols in rows:
        grid = st.columns(len(row_cols))
        for col_widget, col_name in zip(grid, row_cols):
            unique_vals = sorted(df[col_name].astype(str).unique().tolist())
            unique_vals = [v for v in unique_vals if v.strip()]
            with col_widget:
                chosen = st.multiselect(
                    col_name,
                    options=unique_vals,
                    default=[],
                    key=f"cs_filter_{col_name}",
                    placeholder=f"All {col_name}s",
                )
            selections[col_name] = chosen

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    # ── Apply filters ────────────────────────────────────────────────────────
    filtered_df = _apply_filters(df, selections, search_text)

    result_count = len(filtered_df)
    st.markdown(
        f'<p class="va-section-label">📋 Results — {result_count:,} row(s)</p>',
        unsafe_allow_html=True,
    )

    st.dataframe(filtered_df, use_container_width=True, height=420)

    # ── Download filtered data ────────────────────────────────────────────────
    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    dl1, dl2 = st.columns(2)

    with dl1:
        csv_buf = io.StringIO()
        filtered_df.to_csv(csv_buf, index=False)
        st.download_button(
            "📥 Download as CSV",
            data=csv_buf.getvalue().encode(),
            file_name="Filtered_Commentary.csv",
            mime="text/csv",
            key="cs_dl_csv",
        )

    with dl2:
        xl_buf = io.BytesIO()
        with pd.ExcelWriter(xl_buf, engine="openpyxl") as w:
            filtered_df.to_excel(w, index=False, sheet_name="Filtered")
        st.download_button(
            "📥 Download as Excel",
            data=xl_buf.getvalue(),
            file_name="Filtered_Commentary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="cs_dl_xlsx",
        )
