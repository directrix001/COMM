"""
tabs/tab1_mapping.py
────────────────────
Tab 1 — Tagetik Mapping

Renders the file-upload UI, runs the mapping pipeline,
stores the result in session_state.final_db, and offers
CSV / Excel download buttons.

Public API
----------
render()   — call inside  `with tab1:` in app.py
"""

from __future__ import annotations

import io
import os
import time

import pandas as pd
import streamlit as st

from utils.data_helpers import (
    cached_generate_mapping,
    cached_read_and_normalise,
    get_month_cols,
)
from utils.constants import MAPPING_PATH


def render() -> None:
    st.markdown('<p class="va-section-label">📂 Upload Monthly Excel</p>', unsafe_allow_html=True)

    uploaded_monthly = st.file_uploader(
        "Drop your monthly Excel file here (.xlsx)",
        type=["xlsx", "xls"],
        key="monthly_upload",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    process_btn = st.button("⚙️ Generate Mapping", key="process_btn")

    if process_btn and uploaded_monthly is not None:
        try:
            progress_bar = st.progress(0, text="Initialising…")
            time.sleep(0.1)
            progress_bar.progress(10, text="Reading Excel file…")

            file_bytes = uploaded_monthly.read()

            progress_bar.progress(30, text="Normalising headers…")
            _df_check = cached_read_and_normalise(file_bytes)
            if not get_month_cols(_df_check):
                progress_bar.empty()
                st.error("No month columns detected. Ensure columns like '1-Apr', '2-May' exist.")
                return

            progress_bar.progress(50, text="Computing MTD / YTD…")
            mapping_mtime = os.path.getmtime(MAPPING_PATH) if os.path.exists(MAPPING_PATH) else 0.0

            progress_bar.progress(65, text="Loading & merging mapping file…")

            # Surface mapping-column mismatch warning
            mapping_col_check = None
            if os.path.exists(MAPPING_PATH):
                try:
                    mapping_col_check = pd.read_excel(MAPPING_PATH, engine="openpyxl").columns.tolist()
                except Exception:
                    pass

            progress_bar.progress(80, text="Finalising output…")
            df_final = cached_generate_mapping(file_bytes, mapping_mtime)

            if mapping_col_check is not None:
                req1 = {"Entity_desc", "Region", "Entity", "Market"}
                req2 = {"CostCat description", "OH/LC"}
                if not (req1.issubset(mapping_col_check) and req2.issubset(mapping_col_check)):
                    st.warning("Mapping columns mismatch — proceeding without mapping.")

            progress_bar.progress(100, text="Done ✓")
            time.sleep(0.4)
            progress_bar.empty()

            st.session_state.final_db = df_final
            st.success(
                f"✅ Mapping generated — {len(df_final):,} rows × {len(df_final.columns)} columns"
            )
            st.toast("Switch to the 📈 Variance Analysis tab to begin analysis.", icon="➡️")

        except Exception as e:
            st.error(f"Mapping error: {e}")

    elif process_btn and uploaded_monthly is None:
        st.warning("Please upload a monthly Excel file first.")

    # ── Preview & downloads ──────────────────────────────────────────────────
    if st.session_state.get("final_db") is not None:
        st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
        st.markdown('<p class="va-section-label">📋 Preview (top 100 rows)</p>', unsafe_allow_html=True)
        with st.expander("Show generated Mapping", expanded=False):
            st.dataframe(st.session_state.final_db.head(100), use_container_width=True, height=280)

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_buf = io.StringIO()
            st.session_state.final_db.to_csv(csv_buf, index=False)
            st.download_button(
                "📥 Download CSV",
                csv_buf.getvalue().encode(),
                "mapping_output.csv",
                "text/csv",
            )
        with col_dl2:
            xl_buf = io.BytesIO()
            with pd.ExcelWriter(xl_buf, engine="openpyxl") as w:
                st.session_state.final_db.to_excel(w, index=False, sheet_name="mapping_output")
            st.download_button(
                "📥 Download Excel",
                xl_buf.getvalue(),
                "mapping_output.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
