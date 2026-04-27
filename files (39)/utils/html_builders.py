"""
utils/html_builders.py
──────────────────────
HTML builders for the pivot table and hotspot cards.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from utils.formatting import fmt_num, fmt_num_full, fmt_pct, variance_color_class


def build_pivot_html(
    leaf_df: pd.DataFrame,
    group_cols: List[str],
    header_a: str,
    header_b: str,
    favorable_is_lower: bool = True,
) -> str:
    if leaf_df is None or leaf_df.empty:
        return "<p>No data.</p>"

    df_sorted = leaf_df.sort_values(group_cols).reset_index(drop=True)

    def sums(part):
        a = float(part["A"].sum())
        b = float(part["B"].sum())
        d = a - b
        p = (d / b) if b != 0 else float("nan")
        return a, b, d, p

    def vc(v):
        return variance_color_class(v, favorable_is_lower)

    n_dim = len(group_cols)
    rows_html = []

    th_dims = "".join(f'<th class="left">{c}</th>' for c in group_cols)
    th_nums = f"<th>{header_a}</th><th>{header_b}</th><th>Δ (A−B)</th><th>Δ% vs B</th>"
    rows_html.append(f"<thead><tr>{th_dims}{th_nums}</tr></thead>")
    rows_html.append("<tbody>")

    A_t, B_t, D_t, P_t = sums(df_sorted)
    gd_dims = f'<td class="label-cell" colspan="{n_dim}"><strong>GRAND TOTAL</strong></td>'
    rows_html.append(
        f'<tr class="grand">{gd_dims}'
        f'<td class="num">{fmt_num_full(A_t)}</td>'
        f'<td class="num">{fmt_num_full(B_t)}</td>'
        f'<td class="num {vc(D_t)}">{fmt_num_full(D_t)}</td>'
        f'<td class="num {vc(P_t)}">{fmt_pct(P_t)}</td>'
        f"</tr>"
    )

    if n_dim == 1:
        col = group_cols[0]
        for val in df_sorted[col].astype(str).fillna("").unique():
            part = df_sorted[df_sorted[col].astype(str).fillna("") == val]
            a, b, d, p = sums(part)
            rows_html.append(
                f'<tr class="detail">'
                f'<td class="label-cell">{val}</td>'
                f'<td class="num">{fmt_num_full(a)}</td>'
                f'<td class="num">{fmt_num_full(b)}</td>'
                f'<td class="num {vc(d)}">{fmt_num_full(d)}</td>'
                f'<td class="num {vc(p)}">{fmt_pct(p)}</td>'
                f"</tr>"
            )
    else:
        def recurse_html(sub_df, level):
            col = group_cols[level]
            is_second_last = level == n_dim - 2
            css = f"lvl{level + 1}-header"

            for val in sub_df[col].astype(str).fillna("").unique():
                part = sub_df[sub_df[col].astype(str).fillna("") == val]
                indent = f"indent{level}" if level < 3 else "indent3"
                blank_cols_before = "".join("<td></td>" for _ in range(level))
                label_td = (
                    f'<td class="label-cell {indent}" colspan="{n_dim - level}">'
                    f"<strong>{val}</strong></td>"
                )
                rows_html.append(
                    f'<tr class="{css}">{blank_cols_before}{label_td}'
                    f"<td></td><td></td><td></td><td></td></tr>"
                )

                if is_second_last:
                    last_col = group_cols[-1]
                    for lv in part[last_col].astype(str).fillna("").unique():
                        part2 = part[part[last_col].astype(str).fillna("") == lv]
                        a, b, d, p = sums(part2)
                        blanks = "".join("<td></td>" for _ in range(n_dim - 1))
                        indent2 = f"indent{level + 1}" if level + 1 < 3 else "indent3"
                        rows_html.append(
                            f'<tr class="detail">{blanks}'
                            f'<td class="label-cell {indent2}">{lv}</td>'
                            f'<td class="num">{fmt_num_full(a)}</td>'
                            f'<td class="num">{fmt_num_full(b)}</td>'
                            f'<td class="num {vc(d)}">{fmt_num_full(d)}</td>'
                            f'<td class="num {vc(p)}">{fmt_pct(p)}</td>'
                            f"</tr>"
                        )
                else:
                    recurse_html(part, level + 1)

                a, b, d, p = sums(part)
                sub_blanks = "".join("<td></td>" for _ in range(level))
                sub_indent = f"indent{level}" if level < 3 else "indent3"
                rows_html.append(
                    f'<tr class="subtotal">{sub_blanks}'
                    f'<td class="label-cell {sub_indent}" colspan="{n_dim - level}">'
                    f"<em>{val} — Total</em></td>"
                    f'<td class="num">{fmt_num_full(a)}</td>'
                    f'<td class="num">{fmt_num_full(b)}</td>'
                    f'<td class="num {vc(d)}">{fmt_num_full(d)}</td>'
                    f'<td class="num {vc(p)}">{fmt_pct(p)}</td>'
                    f"</tr>"
                )

        recurse_html(df_sorted, 0)

    rows_html.append("</tbody>")
    table_content = "\n".join(rows_html)
    return f"""
<div class="pivot-wrap" style="overflow-x:auto; max-height:620px; overflow-y:auto;">
  <table class="pivot-table">{table_content}</table>
</div>
"""


def build_hotspot_cards(
    leaf_df: pd.DataFrame,
    group_fields: List[str],
    favorable_is_lower: bool,
) -> str:
    if leaf_df is None or leaf_df.empty or not group_fields:
        return ""

    last_dim = group_fields[-1]
    agg = (
        leaf_df.groupby(last_dim, dropna=False)
        .agg(A=("A", "sum"), B=("B", "sum"))
        .reset_index()
    )
    agg["delta"] = agg["A"] - agg["B"]
    agg["pct"] = np.where(agg["B"] == 0, np.nan, agg["delta"] / agg["B"])

    sorted_agg = (
        agg.sort_values("delta", ascending=False).head(4)
        if favorable_is_lower
        else agg.sort_values("delta", ascending=True).head(4)
    ).reset_index(drop=True)

    rank_classes = ["r1", "r2", "r3", "r4"]
    rank_labels  = ["#1 Worst", "#2", "#3", "#4"]

    cards_html = ""
    for i, row in sorted_agg.iterrows():
        rc        = rank_classes[i] if i < 4 else "r4"
        rl        = rank_labels[i]  if i < 4 else f"#{i + 1}"
        name      = str(row[last_dim])[:30] if pd.notna(row[last_dim]) else "–"
        delta_str = fmt_num(row["delta"])
        arrow     = "▲" if row["delta"] > 0 else "▼"
        pct_str   = fmt_pct(row["pct"]) if pd.notna(row["pct"]) else "–"
        a_str     = fmt_num(row["A"])
        b_str     = fmt_num(row["B"])

        cards_html += f"""
<div class="hs-card {rc}">
  <div class="hs-rank">{rl}</div>
  <div class="hs-dim">{last_dim}</div>
  <div class="hs-name" title="{name}">{name}</div>
  <div class="hs-delta">{arrow} {delta_str}</div>
  <div class="hs-meta">A: {a_str} &nbsp;|&nbsp; B: {b_str}</div>
  <div class="hs-meta">Δ% vs B: {pct_str}</div>
</div>"""

    return f'<div class="hs-row">{cards_html}</div>'
