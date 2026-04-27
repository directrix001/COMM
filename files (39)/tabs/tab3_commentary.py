"""
tabs/tab3_commentary.py
───────────────────────
Tab 3 — AI Commentary Generator

Runs a LangGraph recursive drill-down agent (Azure OpenAI)
on the Tab 2 pivot data (or an independently uploaded file)
and produces executive commentary, RCA, and a PPTX deck.

Public API
----------
render()   — call inside  `with tab3:` in app.py
"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils.ai_engine import (
    azure_env_ok,
    build_graph,
    count_leaf_nodes,
    generate_ppt_deck,
    render_trace_tree,
)
from utils.database import handle_run_feedback_click, save_run


def render() -> None:
    st.markdown('<p class="va-section-label">🤖 AI-Powered Commentary Generator</p>', unsafe_allow_html=True)
    st.markdown(
        "Generates executive-level variance commentary using a **recursive drill-down** methodology "
        "powered by **Azure OpenAI** via **LangGraph**. By default, uses the pivot data from Tab 2 — "
        "or upload an independent file below."
    )

    _render_env_status()
    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    cg_df, cg_filename = _render_data_source()
    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    hierarchy_cg, has_variance_col_cg, variance_col_cg, base_scenario_cg, compare_scenario_cg = (
        _render_metric_config(cg_df)
    )
    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    _render_run_button(
        cg_df, cg_filename, hierarchy_cg,
        has_variance_col_cg, variance_col_cg,
        base_scenario_cg, compare_scenario_cg,
    )

    if st.session_state.get("analysis_result") is not None:
        _render_results(hierarchy_cg)


# ─── Private helpers ─────────────────────────────────────────────────────────

def _render_env_status() -> None:
    with st.expander("🔑  Azure OpenAI — Environment Status", expanded=False):
        env_keys = {
            "AZURE_OPENAI_ENDPOINT":    os.getenv("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_KEY":         os.getenv("AZURE_OPENAI_KEY"),
            "AZURE_OPENAI_DEPLOYMENT":  os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        }
        all_ok = all(v for v in env_keys.values())
        badges_html = ""
        for k, v in env_keys.items():
            cls    = "ok" if v else "missing"
            icon   = "✅" if v else "❌"
            masked = (v[:6] + "…") if v else "NOT SET"
            badges_html += f'<span class="cg-env-badge {cls}">{icon} {k} = {masked}</span>'
        st.markdown(badges_html, unsafe_allow_html=True)
        if not all_ok:
            st.markdown(
                '<div class="cg-status-warn">⚠️ One or more Azure OpenAI environment variables are missing.</div>',
                unsafe_allow_html=True,
            )
            st.code(
                "AZURE_OPENAI_ENDPOINT=https://...\n"
                "AZURE_OPENAI_KEY=...\n"
                "AZURE_OPENAI_DEPLOYMENT=...\n"
                "AZURE_OPENAI_API_VERSION=2024-02-15-preview",
                language="bash",
            )
        else:
            st.markdown(
                '<div class="cg-status-ok">✅ All Azure OpenAI environment variables are set.</div>',
                unsafe_allow_html=True,
            )


def _render_data_source():
    tab2_available = (
        st.session_state.get("leaf_df") is not None
        and st.session_state.get("var_context") is not None
    )

    cg_df       = None
    cg_filename = "pivot_data"

    with st.expander("📂  Data Source", expanded=True):
        if tab2_available:
            ctx_t2   = st.session_state.var_context
            tab2_info = (
                f"Period: **{ctx_t2['sel_period']}** · "
                f"A: **{ctx_t2['scenario_a']}** · "
                f"B: **{ctx_t2['scenario_b']}** · "
                f"Rows: **{len(st.session_state.leaf_df):,}**"
            )
            st.markdown(
                f'<div class="cg-status-ok">✅ Tab 2 pivot data ready — {tab2_info}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="cg-status-warn">ℹ️ No Tab 2 pivot data found. '
                "Run Variance Analysis first, or upload a file below.</div>",
                unsafe_allow_html=True,
            )

        cg_src = st.radio(
            "Choose data source for commentary",
            ["🔗  Use Tab 2 Pivot Data (auto)", "📁  Upload independent file (CSV / Excel)"],
            key="cg_src_radio",
            index=0 if tab2_available else 1,
        )

        if cg_src == "🔗  Use Tab 2 Pivot Data (auto)" and tab2_available:
            cg_df       = st.session_state.leaf_df.copy()
            cg_filename = "pivot_data"
            with st.expander("👁️  Preview pivot data (top 20 rows)", expanded=False):
                st.dataframe(cg_df.head(20), use_container_width=True, height=220)
        else:
            cg_upload = st.file_uploader(
                "Upload CSV or Excel file", type=["csv", "xlsx", "xls"], key="cg_upload"
            )
            if cg_upload:
                try:
                    cg_filename = cg_upload.name
                    if cg_upload.name.endswith(".csv"):
                        cg_df = pd.read_csv(cg_upload)
                    else:
                        raw_bytes    = cg_upload.getvalue()
                        xls          = pd.ExcelFile(io.BytesIO(raw_bytes))
                        chosen_sheet = (
                            st.selectbox("Select sheet", xls.sheet_names, key="cg_sheet")
                            if len(xls.sheet_names) > 1
                            else xls.sheet_names[0]
                        )
                        cg_df = pd.read_excel(
                            io.BytesIO(raw_bytes), sheet_name=chosen_sheet, engine="openpyxl"
                        )
                    st.success(f"✅ Loaded — {len(cg_df):,} rows × {len(cg_df.columns)} columns")
                    with st.expander("👁️  Preview uploaded data (top 20 rows)", expanded=False):
                        st.dataframe(cg_df.head(20), use_container_width=True, height=220)
                except Exception as e:
                    st.error(f"File load error: {e}")

    return cg_df, cg_filename


def _render_metric_config(cg_df):
    has_variance_col_cg = True
    variance_col_cg     = ""
    base_scenario_cg    = ""
    compare_scenario_cg = ""
    hierarchy_cg        = []

    tab2_available = (
        st.session_state.get("leaf_df") is not None
        and st.session_state.get("var_context") is not None
    )
    cg_src = st.session_state.get("cg_src_radio", "🔗  Use Tab 2 Pivot Data (auto)")

    with st.expander("⚙️  Metric Configuration", expanded=True):
        if cg_df is not None:
            all_cols_cg = cg_df.columns.tolist()
            num_cols_cg = cg_df.select_dtypes(include=["number"]).columns.tolist()
            cat_cols_cg = cg_df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

            mc1, mc2 = st.columns(2)

            with mc1:
                st.markdown("**Variance Metric**")
                has_variance_col_cg = st.checkbox("Variance column already present?", value=True, key="cg_has_var")

                if has_variance_col_cg:
                    preferred_var = "Δ (A-B)" if "Δ (A-B)" in num_cols_cg else (
                        next((c for c in num_cols_cg if "var" in c.lower()), num_cols_cg[0] if num_cols_cg else None)
                    )
                    var_idx = num_cols_cg.index(preferred_var) if preferred_var in num_cols_cg else 0
                    variance_col_cg = st.selectbox(
                        "Select Variance Column", num_cols_cg, index=var_idx, key="cg_var_col"
                    )
                else:
                    st.caption("Variance will be calculated as (Base − Compare)")
                    base_scenario_cg    = st.selectbox("Base Scenario Column",    num_cols_cg, key="cg_base")
                    compare_scenario_cg = st.selectbox("Compare Scenario Column", num_cols_cg, key="cg_compare")

            with mc2:
                st.markdown("**Drill-Down Hierarchy**")
                default_hierarchy_cg = []
                if cg_src == "🔗  Use Tab 2 Pivot Data (auto)" and tab2_available:
                    gf = st.session_state.var_context.get("group_fields", [])
                    default_hierarchy_cg = [c for c in gf if c in all_cols_cg]
                else:
                    default_hierarchy_cg = [c for c in cat_cols_cg if c in all_cols_cg]

                hierarchy_cg = st.multiselect(
                    "Hierarchy Flow (left = top level → right = leaf reason)",
                    options=all_cols_cg,
                    default=default_hierarchy_cg,
                    key="cg_hierarchy",
                    help="Agent groups by the first column, drills through middle levels, "
                         "reports Top-5 from the LAST column.",
                )
                st.caption(f"ℹ️  {len(hierarchy_cg)} level(s) selected.")
        else:
            st.info("Load a data source above to configure metrics.")

    return hierarchy_cg, has_variance_col_cg, variance_col_cg, base_scenario_cg, compare_scenario_cg


def _render_run_button(
    cg_df, cg_filename, hierarchy_cg,
    has_variance_col_cg, variance_col_cg,
    base_scenario_cg, compare_scenario_cg,
) -> None:
    run_col, hint_col = st.columns([1, 3])
    with run_col:
        cg_run_btn = st.button(
            "🧠  Generate Commentary",
            key="cg_run_btn",
            disabled=(cg_df is None or not azure_env_ok()),
        )
    with hint_col:
        if not azure_env_ok():
            st.markdown('<span style="color:#dc2626;font-size:.8rem;">⚠️ Azure OpenAI env vars missing.</span>', unsafe_allow_html=True)
        elif cg_df is None:
            st.markdown('<span style="color:#6b7fa3;font-size:.8rem;">Load data and configure metrics to enable commentary.</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="color:#059669;font-size:.8rem;">✅ Ready — click Generate Commentary to run the AI agent.</span>', unsafe_allow_html=True)

    if not cg_run_btn:
        return

    if not hierarchy_cg:
        st.warning("Select at least one column in the Hierarchy.")
        return
    if has_variance_col_cg and not variance_col_cg:
        st.warning("Select a variance column.")
        return
    if not has_variance_col_cg and (not base_scenario_cg or not compare_scenario_cg):
        st.warning("Select both Base and Compare scenario columns.")
        return

    st.session_state.analysis_result      = None
    st.session_state.run_feedback_submitted = False

    prog_cg = st.progress(0, text="🔄 Initialising LangGraph agent…")
    try:
        prog_cg.progress(20, text="📐 Building drill-down trace…")
        app_graph = build_graph()

        prog_cg.progress(40, text="🧮 Running branched variance engine…")
        inputs = {
            "df":               cg_df,
            "hierarchy_cols":   hierarchy_cg,
            "has_variance_col": has_variance_col_cg,
            "variance_col":     variance_col_cg,
            "base_scenario":    base_scenario_cg,
            "compare_scenario": compare_scenario_cg,
            "path_trace":       [],
            "final_level_data": [],
            "tree_data":        [],
            "final_summary":    "",
        }

        prog_cg.progress(65, text="🤖 Calling Azure OpenAI for synthesis…")
        result = app_graph.invoke(inputs)

        prog_cg.progress(100, text="✅ Commentary ready!")
        time.sleep(0.4)
        prog_cg.empty()

        st.session_state.analysis_result = result
        st.session_state.cg_report       = result.get("final_summary", "")
        st.session_state.cg_trace        = result.get("path_trace", [])

        if "aborted" not in result.get("final_summary", "").lower() and \
           "error"   not in result.get("final_summary", "").lower():
            total_var_str = (
                result["path_trace"][0].replace("Overall Total Variance: ", "")
                if result.get("path_trace") else "N/A"
            )
            run_id = save_run(cg_filename, hierarchy_cg, total_var_str, result.get("final_summary", ""))
            st.session_state.current_run_id = run_id

        st.toast("Commentary generated! Scroll down to view.", icon="📝")

    except Exception as e:
        prog_cg.empty()
        st.error(f"Commentary generation failed: {e}")


def _render_results(hierarchy_cg) -> None:
    result = st.session_state.analysis_result
    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    if "aborted" in result.get("final_summary", "").lower() or \
       "error"   in result.get("final_summary", "").lower():
        st.error(result.get("final_summary", ""))
        return

    summary_raw  = result.get("final_summary", "")
    exec_summary = summary_raw
    rca_text     = ""
    comm_text    = ""

    if "---ROOT CAUSE ANALYSIS---" in summary_raw:
        parts        = summary_raw.split("---ROOT CAUSE ANALYSIS---")
        exec_summary = parts[0].replace("Executive Summary:", "").strip()
        remainder    = parts[1]
        if "---CATEGORY COMMENTARY---" in remainder:
            rca_parts = remainder.split("---CATEGORY COMMENTARY---")
            rca_text  = rca_parts[0].strip()
            comm_text = rca_parts[1].strip()
        else:
            rca_text = remainder.strip()

    total_var_str = (
        result["path_trace"][0].replace("Overall Total Variance: ", "")
        if result.get("path_trace") else "N/A"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Variance",   total_var_str)
    c2.metric("Hierarchy Levels", str(len(hierarchy_cg)))
    c3.metric("Primary Branches", str(len(result.get("tree_data", []))))
    c4.metric("Final Leaf Nodes", str(count_leaf_nodes(result.get("tree_data", []))))

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📋 Executive Summary")
        st.info(exec_summary)
    with col_right:
        st.subheader("🌳 Recursive Drill-Down Trace")
        if result.get("path_trace"):
            st.caption(result["path_trace"][0])
        render_trace_tree(result.get("tree_data", []))

    if rca_text:
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("🔍 Root Cause Analysis")
        st.success(rca_text)

    if comm_text:
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("💡 Category Commentary")
        st.info(comm_text)

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">📄 Full AI Report</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cg-report-wrap">{summary_raw.replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">📥 Export Results</p>', unsafe_allow_html=True)

    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "📥 Download Report (.md)",
            data=summary_raw,
            file_name="executive_variance_commentary.md",
            mime="text/markdown",
            key="cg_dl_md",
        )
    with dl2:
        st.download_button(
            "📥 Download as Plain Text",
            data=summary_raw,
            file_name="executive_variance_commentary.txt",
            mime="text/plain",
            key="cg_dl_txt",
        )
    with dl3:
        try:
            ppt_file = generate_ppt_deck(
                total_variance=total_var_str,
                exec_summary=exec_summary,
                rca_text=rca_text,
                comm_text=comm_text,
                tree_data=result.get("tree_data", []),
            )
            st.download_button(
                label="📥 Download Deck (.pptx)",
                data=ppt_file,
                file_name=f"Variance_Deck_{datetime.now().strftime('%Y%m%d')}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="cg_dl_pptx",
            )
        except Exception as e:
            st.error(f"PPTX export error: {e}")

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    if st.session_state.get("current_run_id"):
        if st.session_state.get("run_feedback_submitted"):
            st.success("Thank you for your feedback! ✅")
        else:
            st.markdown("##### How did the AI perform on this analysis?")
            fc1, fc2, _ = st.columns([1, 1, 10])
            fc1.button(
                "👍", key="run_up",
                on_click=handle_run_feedback_click,
                args=(st.session_state.current_run_id, 1),
            )
            fc2.button(
                "👎", key="run_down",
                on_click=handle_run_feedback_click,
                args=(st.session_state.current_run_id, -1),
            )

    with st.expander("🧮  Raw Drill-Down Trace", expanded=False):
        trace = st.session_state.get("cg_trace") or []
        if trace:
            for step in trace:
                step_s = str(step).strip()
                if not step_s:
                    st.write("")
                elif step_s.startswith("Error"):
                    st.error(step_s)
                elif "Overall Total Variance" in step_s or "Primary Category" in step_s:
                    st.markdown(f'<div class="cg-trace-block primary">{step_s}</div>', unsafe_allow_html=True)
                elif "Final Level" in step_s:
                    st.markdown(f'<div class="cg-trace-block final">{step_s}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="cg-trace-block">{step_s}</div>', unsafe_allow_html=True)
        else:
            st.info("No trace data available.")
