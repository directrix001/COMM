"""
tabs/tab5_history.py
────────────────────
Tab 5 — Run History

Displays all analysis runs stored in SQLite, allows
viewing full AI summaries and a thumbs-up/down feedback
summary chart.

Public API
----------
render()   — call inside  `with tab5:` in app.py
"""

from __future__ import annotations

import json

import streamlit as st

from utils.database import fetch_run_history


def render() -> None:
    st.markdown('<p class="va-section-label">🗄️ Historical Analysis Runs</p>', unsafe_allow_html=True)

    history_df = fetch_run_history()

    if history_df.empty:
        st.info(
            "No analysis runs found yet. "
            "Run a Commentary Generator analysis to start logging."
        )
        return

    history_df["feedback_status"] = history_df["feedback"].map({1: "👍", -1: "👎", 0: "➖"})

    st.markdown(f"**{len(history_df)} run(s) logged**")
    st.dataframe(
        history_df[["id", "timestamp", "filename", "total_variance", "feedback_status"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">🔍 Run Details</p>', unsafe_allow_html=True)

    selected_run = st.selectbox(
        "Select a Run ID to view full details:",
        history_df["id"].tolist(),
        key="hist_sel",
    )

    if selected_run:
        run_details = history_df[history_df["id"] == selected_run].iloc[0]
        col_h1, col_h2, col_h3 = st.columns(3)
        col_h1.metric("Run ID",   str(run_details["id"]))
        col_h2.metric("Variance", str(run_details["total_variance"]))
        col_h3.metric("Feedback", str(run_details["feedback_status"]))

        st.markdown(
            f"**File:** `{run_details['filename']}` "
            f"&nbsp;|&nbsp; **Ran at:** `{run_details['timestamp']}`"
        )

        try:
            hier = json.loads(run_details["hierarchy"])
            st.markdown(f"**Hierarchy:** {' → '.join(hier)}")
        except Exception:
            st.markdown(f"**Hierarchy:** {run_details['hierarchy']}")

        with st.expander("📄 Full AI Summary", expanded=True):
            st.markdown(
                f'<div class="cg-report-wrap">'
                f'{str(run_details["summary"]).replace(chr(10), "<br>")}'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">📊 Feedback Overview</p>', unsafe_allow_html=True)

    fb_counts  = history_df["feedback_status"].value_counts()
    fb_col1, fb_col2, fb_col3 = st.columns(3)
    fb_col1.metric("👍 Positive",  fb_counts.get("👍", 0))
    fb_col2.metric("👎 Negative",  fb_counts.get("👎", 0))
    fb_col3.metric("➖ No Rating", fb_counts.get("➖", 0))
