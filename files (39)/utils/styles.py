"""
utils/styles.py
───────────────
CSS injection and header/footer rendering.
Centralised here so adding a new tab never touches style code.
"""

from __future__ import annotations

import base64
import os

import streamlit as st

from utils.constants import FOOTER_H, HEADER_H

# ─── Logo helpers ─────────────────────────────────────────────────────────────

NISSAN_LOGO_PATH  = "uzsbf2-nissan-logo-picture.png"
GENPACT_LOGO_PATH = "Logo2.png"


def _img_to_b64(path: str) -> str | None:
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def _logo_tag(b64: str | None, alt: str, height: int = 44) -> str:
    if b64:
        return f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="height:{height}px;object-fit:contain;">'
    color = "#c8102e" if alt == "Nissan" else "#00a651"
    return f'<span style="color:{color};font-weight:800;font-size:1.1rem;letter-spacing:2px;">{alt.upper()}</span>'


# ─── Public API ───────────────────────────────────────────────────────────────

def inject_css() -> None:
    """Inject the full application CSS into the Streamlit page."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [data-testid="stAppViewContainer"] {{
    background: #070c14 !important;
    font-family: 'Sora', sans-serif !important;
}}
[data-testid="stMain"] {{
    background: #f1f5fb !important;
}}
[data-testid="stMain"] > div:first-child {{
    background: #f1f5fb !important;
    color: #0f1f3d !important;
    padding-top: {HEADER_H + 22}px !important;
    padding-bottom: {FOOTER_H + 22}px !important;
    padding-left: 48px !important;
    padding-right: 48px !important;
}}
[data-testid="stMain"] p,
[data-testid="stMain"] span,
[data-testid="stMain"] label,
[data-testid="stMain"] div {{ color: #0f1f3d; }}

#MainMenu, header[data-testid="stHeader"], footer {{ display:none !important; }}
[data-testid="stSidebar"] {{ display:none !important; }}

.va-header {{
    position: fixed; top: 0; left: 0; right: 0;
    height: {HEADER_H}px; background: #070c14;
    border-bottom: 1px solid #1a2744;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 32px; z-index: 9999;
    box-shadow: 0 4px 32px rgba(0,0,0,.6);
}}
.va-header-center {{
    display: flex; flex-direction: column; align-items: center; gap: 1px; flex: 1;
}}
.va-header-title {{
    font-family: 'Sora', sans-serif;
    font-size: .95rem; font-weight: 800; letter-spacing: .18em;
    color: #ffffff !important; text-transform: uppercase;
}}
.va-header-title em {{ color: #60a5fa !important; font-style: normal; }}
.va-header-sub {{
    font-size: .6rem; letter-spacing: .14em;
    color: #c8d6f0 !important; text-transform: uppercase;
}}

.va-footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    height: {FOOTER_H}px; background: #070c14;
    border-top: 1px solid #1a2744;
    display: flex; align-items: center; justify-content: center;
    gap: 24px; z-index: 9999; font-size: .68rem; letter-spacing: .06em;
}}
.va-footer span {{ color: #d0ddf5 !important; }}
.va-footer a {{ color: #93c5fd !important; text-decoration: none; }}
.va-footer-sep {{ color: #3a4f78 !important; }}

.va-section-label {{
    font-family: 'Sora', sans-serif;
    font-size: .65rem; font-weight: 700; letter-spacing: .18em;
    text-transform: uppercase; color: #2563eb !important;
    margin-bottom: 10px; display: flex; align-items: center; gap: 8px;
}}
.va-section-label::after {{ content: ''; flex: 1; height: 1px; background: #d1dced; }}

.va-divider {{ border: none; border-top: 1px solid #d8e2f0; margin: 22px 0; }}

.va-card {{
    background: #ffffff; border: 1px solid #dce6f5;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(15,31,61,.06);
}}
.va-metric-card {{
    background: #fff; border: 1px solid #dce6f5;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(15,31,61,.05);
}}
.va-metric-card .mlabel {{
    font-size: .62rem; letter-spacing: .1em; text-transform: uppercase;
    color: #6b7fa3 !important; margin-bottom: 5px;
}}
.va-metric-card .mvalue {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.35rem; font-weight: 600; color: #0f1f3d !important;
}}
.va-metric-card .msub {{ font-size: .68rem; color: #8a99bc !important; margin-top: 3px; }}

.hs-row {{ display: grid; grid-template-columns: repeat(4,1fr); gap:12px; margin-bottom:18px; }}
.hs-card {{ border-radius:10px; padding:12px 14px; border:1px solid; position:relative; overflow:hidden; }}
.hs-card .hs-rank {{ position:absolute; top:8px; right:10px; font-size:.6rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; opacity:.7; }}
.hs-card .hs-dim  {{ font-size:.58rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin-bottom:4px; opacity:.75; }}
.hs-card .hs-name {{ font-family:'Sora',sans-serif; font-size:.78rem; font-weight:700; margin-bottom:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.hs-card .hs-delta {{ font-family:'JetBrains Mono',monospace; font-size:1.05rem; font-weight:700; margin-bottom:2px; }}
.hs-card .hs-meta  {{ font-size:.62rem; opacity:.7; margin-top:4px; }}
.hs-card.r1 {{ background:#fef2f2; border-color:#dc2626; color:#7f1d1d !important; }}
.hs-card.r1 .hs-delta {{ color:#dc2626 !important; }}
.hs-card.r2 {{ background:#fff5f5; border-color:#f87171; color:#991b1b !important; }}
.hs-card.r2 .hs-delta {{ color:#ef4444 !important; }}
.hs-card.r3 {{ background:#fff8f8; border-color:#fca5a5; color:#b91c1c !important; }}
.hs-card.r3 .hs-delta {{ color:#f87171 !important; }}
.hs-card.r4 {{ background:#fffbfb; border-color:#fecaca; color:#c4392a !important; }}
.hs-card.r4 .hs-delta {{ color:#fca5a5 !important; }}

.pivot-wrap {{ background:#fff; border:1px solid #dce6f5; border-radius:12px; overflow:hidden; box-shadow:0 1px 4px rgba(15,31,61,.06); }}
.pivot-table {{ width:100%; border-collapse:collapse; font-size:.82rem; }}
.pivot-table thead th {{ background:#0f1f3d; color:#e8edf8 !important; font-family:'Sora',sans-serif; font-weight:600; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; padding:10px 14px; text-align:right; white-space:nowrap; border:none; }}
.pivot-table thead th.left {{ text-align:left; }}
.pivot-table tbody tr.grand {{ background:#1e3a5f; border-bottom:2px solid #2563eb; }}
.pivot-table tbody tr.grand td {{ color:#e8edf8 !important; font-weight:700; font-family:'JetBrains Mono',monospace; padding:10px 14px; }}
.pivot-table tbody tr.lvl1-header {{ background:#dde8f8; border-bottom:1px solid #c4d4ed; }}
.pivot-table tbody tr.lvl1-header td {{ font-weight:700; color:#0d2a5a !important; padding:8px 14px; font-size:.8rem; }}
.pivot-table tbody tr.lvl2-header {{ background:#eef4fc; border-bottom:1px solid #d4e3f4; }}
.pivot-table tbody tr.lvl2-header td {{ font-weight:600; color:#1a3460 !important; padding:7px 14px; font-size:.78rem; }}
.pivot-table tbody tr.subtotal {{ background:#f0f5fd; border-top:1px solid #c4d4ed; border-bottom:1px solid #c4d4ed; }}
.pivot-table tbody tr.subtotal td {{ font-weight:600; color:#0f1f3d !important; font-family:'JetBrains Mono',monospace; padding:7px 14px; font-size:.78rem; font-style:italic; }}
.pivot-table tbody tr.detail {{ background:#fff; border-bottom:1px solid #eff3fb; }}
.pivot-table tbody tr.detail:hover {{ background:#f5f9ff; }}
.pivot-table tbody tr.detail td {{ color:#233057 !important; padding:6px 14px; font-family:'JetBrains Mono',monospace; font-size:.78rem; }}
.pivot-table td.label-cell {{ text-align:left; font-family:'Sora',sans-serif !important; }}
.pivot-table td.num {{ text-align:right; }}
.pivot-table td.fav {{ color:#059669 !important; font-weight:700; }}
.pivot-table td.adv {{ color:#dc2626 !important; font-weight:700; }}
.pivot-table td.neutral {{ color:#6b7fa3 !important; }}
.pivot-table td.indent1 {{ padding-left:28px !important; }}
.pivot-table td.indent2 {{ padding-left:46px !important; }}
.pivot-table td.indent3 {{ padding-left:64px !important; }}

[data-testid="stFileUploader"] {{ background:#fff !important; border:1.5px dashed #93c5fd !important; border-radius:12px !important; padding:20px 28px !important; box-shadow:0 1px 4px rgba(59,130,246,.06) !important; }}
[data-testid="stFileUploader"] label, [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] p {{ color:#0f1f3d !important; }}

[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background:#fff !important; border:1px solid #93c5fd !important; border-radius:8px !important; color:#0f1f3d !important; }}
[data-testid="stMain"] .stSelectbox label,
[data-testid="stMain"] .stMultiSelect label {{ color:#0f1f3d !important; font-weight:500; font-size:.82rem; }}

[data-testid="stTabs"] [role="tablist"] {{ gap:4px; border-bottom:2px solid #dce6f5; }}
[data-testid="stTabs"] [role="tab"] {{ font-family:'Sora',sans-serif; font-weight:600; font-size:.78rem; letter-spacing:.08em; color:#6b7fa3 !important; padding:8px 20px; border-radius:8px 8px 0 0; border:none; background:transparent; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ color:#1d4ed8 !important; background:#eff5ff; border-bottom:2px solid #2563eb; }}

[data-testid="stExpander"] {{ background:#fff !important; border:1px solid #dce6f5 !important; border-radius:10px !important; }}
[data-testid="stExpander"] summary {{ font-weight:600 !important; color:#0f1f3d !important; }}

[data-testid="stButton"] button {{ background:#dc2626 !important; color:#ffffff !important; border:none !important; border-radius:8px !important; font-family:'Sora',sans-serif !important; font-weight:600 !important; letter-spacing:.04em !important; padding:8px 22px !important; font-size:.8rem !important; }}
[data-testid="stButton"] button:hover {{ background:#b91c1c !important; color:#ffffff !important; }}
[data-testid="stButton"] button * {{ color:#ffffff !important; }}

[data-testid="stDownloadButton"] button {{ background:#059669 !important; color:#fff !important; border:none !important; border-radius:8px !important; font-family:'Sora',sans-serif !important; font-weight:600 !important; padding:8px 22px !important; font-size:.8rem !important; }}
[data-testid="stDownloadButton"] button:hover {{ background:#047857 !important; }}

[data-testid="stInfo"] {{ background:#eff6ff !important; border:1px solid #93c5fd !important; border-radius:8px !important; color:#1d4ed8 !important; }}
[data-testid="stWarning"] {{ background:#fffbeb !important; border:1px solid #fbbf24 !important; border-radius:8px !important; color:#92400e !important; }}
[data-testid="stSuccess"] {{ background:#ecfdf5 !important; border:1px solid #6ee7b7 !important; border-radius:8px !important; color:#065f46 !important; }}
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {{ color:#0f1f3d !important; }}
[data-testid="stMain"] strong {{ color:#0f1f3d !important; }}

[data-testid="stProgressBar"] > div > div {{ background:#9ca3af !important; }}
[data-testid="stProgressBar"] {{ background:#e5e7eb !important; border-radius:99px !important; }}

.cg-status-ok {{ background:#ecfdf5; border:1px solid #6ee7b7; border-radius:8px; padding:10px 16px; display:flex; align-items:center; gap:10px; font-size:.8rem; color:#065f46 !important; margin-bottom:14px; }}
.cg-status-warn {{ background:#fffbeb; border:1px solid #fbbf24; border-radius:8px; padding:10px 16px; display:flex; align-items:center; gap:10px; font-size:.8rem; color:#92400e !important; margin-bottom:14px; }}
.cg-report-wrap {{ background:#fff; border:1px solid #c4d4ed; border-radius:14px; padding:28px 32px; margin-top:10px; box-shadow:0 2px 12px rgba(15,31,61,.07); font-family:'Sora',sans-serif; line-height:1.7; }}
.cg-report-wrap h3 {{ font-size:.9rem; font-weight:700; letter-spacing:.06em; color:#0f1f3d !important; margin:18px 0 6px; padding-bottom:4px; border-bottom:1px solid #e8edf8; }}
.cg-report-wrap p {{ color:#2d3f60 !important; font-size:.85rem; margin:6px 0; }}
.cg-env-badge {{ display:inline-flex; align-items:center; gap:6px; background:#f0f5fd; border:1px solid #c4d4ed; border-radius:20px; padding:4px 12px; font-size:.68rem; font-weight:600; color:#1d4ed8 !important; margin:3px 4px 3px 0; }}
.cg-env-badge.ok {{ background:#ecfdf5; border-color:#6ee7b7; color:#065f46 !important; }}
.cg-env-badge.missing {{ background:#fef2f2; border-color:#fca5a5; color:#dc2626 !important; }}
.cg-trace-block {{ background:#f8faff; border:1px solid #dce6f5; border-radius:8px; padding:14px 18px; margin-bottom:6px; font-size:.78rem; }}
.cg-trace-block.primary {{ background:#eff5ff; border-color:#93c5fd; font-weight:700; }}
.cg-trace-block.final {{ background:#ecfdf5; border-color:#6ee7b7; }}
</style>
""",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    nissan_b64  = _img_to_b64(NISSAN_LOGO_PATH)
    genpact_b64 = _img_to_b64(GENPACT_LOGO_PATH)
    st.markdown(
        f"""
<div class="va-header">
    <div>{_logo_tag(nissan_b64, "Nissan", 40)}</div>
    <div class="va-header-center">
        <div class="va-header-title">Variance <em>Analysis</em> Tool</div>
        <div class="va-header-sub">Finance Data Pipeline · Scenario Intelligence</div>
    </div>
    <div>{_logo_tag(genpact_b64, "Genpact", 36)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        """
<div class="va-footer">
    <span>© 2025 Genpact · Nissan Partnership</span>
    <span class="va-footer-sep">|</span>
    <span>Variance Analysis Platform</span>
    <span class="va-footer-sep">|</span>
    <span>Confidential &amp; Proprietary</span>
    <span class="va-footer-sep">|</span>
    <a href="#">Privacy Policy</a>
    <span class="va-footer-sep">|</span>
    <a href="#">Support</a>
</div>
""",
        unsafe_allow_html=True,
    )
