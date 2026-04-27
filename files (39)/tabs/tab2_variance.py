"""
tabs/tab2_variance.py
─────────────────────
Tab 2 — Variance Analysis

Loads a data source (mapping output / master DB / two files),
applies filters, runs the pivot, renders hotspot cards &
top/bottom movers, and offers an Excel export.

Public API
----------
render()   — call inside  `with tab2:` in app.py
"""

from __future__ import annotations

import io
import time

import numpy as np
import streamlit as st

from utils.constants import FULL_TO_ABBR, MONTH_TO_FYNUM, PREF_GROUP_ORDER
from utils.data_helpers import (
    cached_apply_filters,
    cached_read_and_normalise,
    cached_run_variance,
    get_filter_options,
    normalize_df_headers,
)
from utils.excel_export import build_excel_export
from utils.formatting import fmt_num
from utils.html_builders import build_hotspot_cards, build_pivot_html


def render() -> None:
    st.markdown('<p class="va-section-label">🗄️ Data Source</p>', unsafe_allow_html=True)

    src_mode = st.selectbox(
        "Select data source mode",
        [
            "Use Generated Output (from Target Mapping)",
            "Upload Master DB (single file with both scenarios)",
            "Upload Two Files (A & B — assign scenario labels)",
        ],
        key="src_mode",
    )

    master_df_loaded = None

    if src_mode == "Use Generated Output (from Target Mapping)":
        if st.session_state.get("final_db") is not None:
            master_df_loaded = normalize_df_headers(st.session_state.final_db)
            st.success(f"✅ Using mapping output — {len(master_df_loaded):,} rows")
        else:
            st.warning("No mapping output found. Go to **Target Mapping** tab and process a file first.")

    elif src_mode == "Upload Master DB (single file with both scenarios)":
        upl_master = st.file_uploader("Upload Master DB (.xlsx)", type=["xlsx", "xls"], key="upl_master")
        if upl_master:
            master_df_loaded = cached_read_and_normalise(upl_master.read())
            st.success(f"✅ Loaded — {len(master_df_loaded):,} rows × {len(master_df_loaded.columns)} columns")

    else:
        col_a_up, col_b_up = st.columns(2)
        with col_a_up:
            upl_a   = st.file_uploader("File for Scenario A (.xlsx)", type=["xlsx", "xls"], key="upl_a")
            label_a = st.text_input("Scenario A label", "Scenario_A", key="label_a")
        with col_b_up:
            upl_b   = st.file_uploader("File for Scenario B (.xlsx)", type=["xlsx", "xls"], key="upl_b")
            label_b = st.text_input("Scenario B label", "Scenario_B", key="label_b")

        if upl_a and upl_b:
            dfa = cached_read_and_normalise(upl_a.read()).copy()
            dfb = cached_read_and_normalise(upl_b.read()).copy()
            dfa["Scenario"] = label_a.strip() or "Scenario_A"
            dfb["Scenario"] = label_b.strip() or "Scenario_B"
            common = list(set(dfa.columns) & set(dfb.columns))
            import pandas as pd
            master_df_loaded = pd.concat([dfa[common], dfb[common]], ignore_index=True)
            st.success(f"✅ Combined — {len(master_df_loaded):,} rows")

    if master_df_loaded is not None:
        st.session_state.master_df = master_df_loaded

    df_master = st.session_state.get("master_df")

    if df_master is None:
        st.info("Load a data source above to begin variance analysis.")
        return

    with st.expander(
        f"📋 Preview data — {len(df_master):,} rows × {len(df_master.columns)} columns",
        expanded=False,
    ):
        st.dataframe(df_master.head(50), use_container_width=True, height=220)

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    scenarios, markets, regions, divisions, entities, lc_oh, month_cols_avail = get_filter_options(df_master)

    if "Scenario" not in df_master.columns:
        st.error(
            "Data must contain a **'Scenario'** column. "
            "Use 'Upload Two Files' mode or ensure your Master DB has a Scenario column."
        )
        return

    avail_group   = [k for k in PREF_GROUP_ORDER if k in df_master.columns]
    default_group = [k for k in ["OH/LC", "Division_Desc", "Function_Desc"] if k in avail_group]

    st.markdown('<p class="va-section-label">🎛️ Filters & Configuration</p>', unsafe_allow_html=True)

    def _month_sort_key(col):
        parts = str(col).split("-")
        if len(parts) == 2:
            mon = parts[1].title()
            return MONTH_TO_FYNUM.get(mon, 99)
        return 99

    def _month_label(col):
        parts = str(col).split("-")
        if len(parts) == 2:
            mon = parts[1].title()
            full = {v: k for k, v in FULL_TO_ABBR.items()}.get(mon, mon)
            return f"{full} ({col})"
        return col

    month_cols_sorted    = sorted(month_cols_avail, key=_month_sort_key)
    month_label_to_col   = {_month_label(c): c for c in month_cols_sorted}
    month_labels         = list(month_label_to_col.keys())

    cfg_p1, cfg_p2, cfg_p3 = st.columns(3)
    with cfg_p1:
        period_mode = st.radio(
            "📅 Analysis Period",
            ["YTD — Year to Date", "MTD — Specific Month"],
            key="period_mode",
            horizontal=True,
        )
    with cfg_p2:
        scenario_a = st.selectbox("📌 Scenario A (Base)", scenarios, index=0, key="sc_a")
    with cfg_p3:
        opts_b     = [s for s in scenarios if s != scenario_a] or scenarios
        scenario_b = st.selectbox("📌 Scenario B (Compare)", opts_b, index=0, key="sc_b")

    if period_mode.startswith("YTD"):
        if "YTD" in df_master.columns:
            sel_period = "YTD"
            st.caption("📌 Using pre-computed **YTD** column.")
        elif month_cols_avail:
            sel_period = "__YTD_CALC__"
            st.caption(f"📌 **YTD** will be computed by summing {len(month_cols_avail)} month columns.")
        else:
            sel_period = None
            st.error("No YTD column or month columns found in data.")
    else:
        if month_labels:
            sel_month_label = st.selectbox(
                "📆 Select Month for MTD",
                month_labels,
                index=len(month_labels) - 1,
                key="sel_mtd_month",
            )
            sel_period = month_label_to_col[sel_month_label]
            st.caption(f"📌 MTD column selected: **{sel_period}**")
        else:
            sel_period = None
            st.error("No month columns found (expected format: '1-Apr', '2-May', …).")

    flt1, flt2, flt3, flt4, flt5 = st.columns(5)
    with flt1:
        sel_markets   = st.multiselect("🌍 Market",   markets,   default=markets,   key="sel_markets")   if markets   else []
    with flt2:
        sel_regions   = st.multiselect("🗺️ Region",   regions,   default=regions,   key="sel_regions")   if regions   else []
    with flt3:
        sel_divisions = st.multiselect("🏢 Division", divisions, default=divisions, key="sel_divisions") if divisions else []
    with flt4:
        sel_entities  = st.multiselect("🏛️ Entity",   entities,  default=entities,  key="sel_entities")  if entities  else []
    with flt5:
        sel_lc_oh     = st.multiselect("🏷️ OH/LC",    lc_oh,     default=lc_oh,     key="sel_lc_oh")     if lc_oh     else []

    cfg4, cfg5 = st.columns([2, 1])
    with cfg4:
        sel_groups = st.multiselect(
            "🔀 Pivot Row Fields (hierarchy — top = highest level)",
            avail_group,
            default=default_group if default_group else avail_group[:2],
            key="sel_groups",
        )
    with cfg5:
        fav_mode = st.radio(
            "✅ Favorable variance when",
            ["A < B  (cost — lower is better)", "A > B  (revenue — higher is better)"],
            key="fav_mode",
        )
        favorable_is_lower = fav_mode.startswith("A < B")

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    run_btn = st.button("▶  Run Variance Analysis", key="run_btn")

    if run_btn:
        if not sel_groups:
            st.warning("Select at least one Pivot Row Field.")
        elif sel_period is None:
            st.error("No valid period column resolved. Check your data.")
        else:
            try:
                prog = st.progress(0, text="🔄 Preparing data…")
                time.sleep(0.05)
                prog.progress(25, text="🔍 Applying filters…")

                df_filtered = cached_apply_filters(
                    df=df_master,
                    scenario_a=scenario_a,
                    scenario_b=scenario_b,
                    sel_markets=tuple(sorted(sel_markets)),
                    sel_regions=tuple(sorted(sel_regions)),
                    sel_divisions=tuple(sorted(sel_divisions)),
                    sel_entities=tuple(sorted(sel_entities)),
                    sel_lc_oh=tuple(sorted(sel_lc_oh)),
                )

                group_fields = list(sel_groups)

                if sel_period != "__YTD_CALC__" and sel_period not in df_filtered.columns:
                    prog.empty()
                    st.error(f"Period column '{sel_period}' not found in data.")
                    return

                prog.progress(60, text="🧮 Aggregating & pivoting…")

                leaf_df, pivot_source_long, period_label = cached_run_variance(
                    df_filtered=df_filtered,
                    group_fields=tuple(group_fields),
                    scenario_a=scenario_a,
                    scenario_b=scenario_b,
                    sel_period=sel_period,
                    month_cols_avail=tuple(month_cols_avail),
                )

                header_a = f"{scenario_a} (A)"
                header_b = f"{scenario_b} (B)"

                prog.progress(100, text="✅ Done!")
                time.sleep(0.4)
                prog.empty()

                st.session_state.leaf_df           = leaf_df
                st.session_state.pivot_source_long = pivot_source_long
                st.session_state.var_context = {
                    "sel_period":         period_label,
                    "sel_markets":        sel_markets,
                    "sel_regions":        sel_regions,
                    "sel_divisions":      sel_divisions,
                    "scenario_a":         scenario_a,
                    "scenario_b":         scenario_b,
                    "header_a":           header_a,
                    "header_b":           header_b,
                    "group_fields":       group_fields,
                    "favorable_is_lower": favorable_is_lower,
                }
                st.session_state.analysis_result = None
                st.session_state.cg_report        = None
                st.session_state.cg_trace         = None

                st.success(f"✅ Variance computed — {len(leaf_df):,} leaf rows")
                st.toast("Variance analysis complete! Scroll down to view results.", icon="📊")

            except Exception as e:
                st.error(f"Error: {e}")

    # ── Results ──────────────────────────────────────────────────────────────
    if st.session_state.get("leaf_df") is not None and st.session_state.get("var_context") is not None:
        _render_results()


def _render_results() -> None:
    ctx          = st.session_state.var_context
    leaf_df      = st.session_state.leaf_df
    group_fields = ctx["group_fields"]
    header_a     = ctx["header_a"]
    header_b     = ctx["header_b"]
    fav_lower    = ctx["favorable_is_lower"]

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)

    total_a   = float(leaf_df["A"].sum())
    total_b   = float(leaf_df["B"].sum())
    total_var = total_a - total_b
    pct_var   = (total_var / total_b * 100) if total_b != 0 else 0.0
    max_var   = float(leaf_df["Δ (A-B)"].abs().max())
    n_fav     = int((leaf_df["Δ (A-B)"] > 0).sum()) if fav_lower else int((leaf_df["Δ (A-B)"] < 0).sum())
    n_adv     = int((leaf_df["Δ (A-B)"] < 0).sum()) if fav_lower else int((leaf_df["Δ (A-B)"] > 0).sum())

    var_color = (
        "#059669"
        if (fav_lower and total_var < 0) or (not fav_lower and total_var > 0)
        else "#dc2626"
    )
    arrow = "▼" if total_var < 0 else "▲"

    k1, k2, k3, k4 = st.columns(4)
    for col_k, label, value, sub in [
        (k1, f"Total {ctx['scenario_a']}", fmt_num(total_a), "Scenario A"),
        (k2, f"Total {ctx['scenario_b']}", fmt_num(total_b), "Scenario B"),
        (
            k3,
            "Net Variance (A−B)",
            f'<span style="color:{var_color}">{arrow} {fmt_num(total_var)}</span>',
            f"{pct_var:+.1f}% vs B",
        ),
        (k4, "Max Single |Δ|", fmt_num(max_var), f"▲ {n_fav} favourable · ▼ {n_adv} adverse"),
    ]:
        with col_k:
            st.markdown(
                f"""
<div class="va-metric-card">
  <div class="mlabel">{label}</div>
  <div class="mvalue">{value}</div>
  <div class="msub">{sub}</div>
</div>""",
                unsafe_allow_html=True,
            )

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    with st.expander(
        f"📊 Pivot Variance · {ctx['sel_period']} · {header_a} vs {header_b}",
        expanded=True,
    ):
        pivot_html = build_pivot_html(leaf_df, group_fields, header_a, header_b, fav_lower)
        st.markdown(pivot_html, unsafe_allow_html=True)

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">🔍 Variance Hotspot Analysis</p>', unsafe_allow_html=True)

    last_dim = group_fields[-1] if group_fields else None

    if last_dim and last_dim in leaf_df.columns and len(leaf_df) > 0:
        st.markdown(f"**Top 4 adverse rows by `{last_dim}` — worst to least (darkest → lightest)**")
        hotspot_html = build_hotspot_cards(leaf_df, group_fields, fav_lower)
        st.markdown(hotspot_html, unsafe_allow_html=True)

        st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
        st.markdown('<p class="va-section-label">📈 Top & Bottom 5 Movers</p>', unsafe_allow_html=True)

        insight_dims = [c for c in group_fields if c in leaf_df.columns]
        top5_cols    = insight_dims[:3] + ["A", "B", "Δ (A-B)", "Δ% vs B"]
        top5_cols    = [c for c in top5_cols if c in leaf_df.columns]

        t5, b5 = st.columns(2)
        with t5:
            st.markdown(f"**Top 5 {'Favourable' if fav_lower else 'Positive'} Variance**")
            top5 = (
                leaf_df.nsmallest(5, "Δ (A-B)") if fav_lower else leaf_df.nlargest(5, "Δ (A-B)")
            )[top5_cols].reset_index(drop=True)
            st.dataframe(top5, use_container_width=True, height=200)

        with b5:
            st.markdown(f"**Top 5 {'Adverse' if fav_lower else 'Negative'} Variance**")
            bot5 = (
                leaf_df.nlargest(5, "Δ (A-B)") if fav_lower else leaf_df.nsmallest(5, "Δ (A-B)")
            )[top5_cols].reset_index(drop=True)
            st.dataframe(bot5, use_container_width=True, height=200)

    st.markdown('<hr class="va-divider">', unsafe_allow_html=True)
    st.markdown('<p class="va-section-label">📥 Export</p>', unsafe_allow_html=True)

    try:
        excel_bytes = build_excel_export(
            leaf_df=leaf_df,
            group_fields=group_fields,
            header_a=header_a,
            header_b=header_b,
            sel_period=ctx["sel_period"],
            sel_markets=ctx["sel_markets"],
            sel_regions=ctx["sel_regions"],
            sel_divisions=ctx["sel_divisions"],
            scenario_a=ctx["scenario_a"],
            scenario_b=ctx["scenario_b"],
            favorable_is_lower=fav_lower,
            pivot_source_long=st.session_state.pivot_source_long,
        )
        safe_period = ctx["sel_period"].replace("/", "-")
        st.download_button(
            "📥 Download Variance Report (Excel)",
            excel_bytes,
            f"variance_report_{safe_period}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(
            "Report includes: README · Variance (Flat) · Pivot (Outline with collapse/expand) · PivotSource"
        )
    except Exception as e:
        st.error(f"Export error: {e}")
