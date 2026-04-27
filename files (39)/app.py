"""
app.py — Main entry point
─────────────────────────
Bootstraps the Streamlit page, injects shared CSS/header/footer,
initialises session-state defaults and the SQLite DB, then
delegates each tab to its own module.

Adding a new tab
────────────────
1. Create  tabs/tab6_myfeature.py  with a  render()  function.
2. Add a new entry to TAB_REGISTRY below.
3. Done — no other file needs touching.
"""

from __future__ import annotations

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# ── Page config (must be the very first Streamlit call) ──────────────────────
st.set_page_config(
    page_title="Variance Analysis Tool",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Shared utilities ─────────────────────────────────────────────────────────
from utils.styles   import inject_css, render_header, render_footer
from utils.database import init_db

# ── Tab modules ──────────────────────────────────────────────────────────────
from tabs import tab1_mapping
from tabs import tab2_variance
from tabs import tab3_commentary
from tabs import tab4_chat
from tabs import tab5_history
from tabs import tab6_comment_search
from tabs import tab7_ppt_upload

# ─────────────────────────────────────────────────────────────────────────────
# TAB REGISTRY
# To add a new tab:  append a (label, module) tuple here and create the module.
# ─────────────────────────────────────────────────────────────────────────────
TAB_REGISTRY = [
    ("🗂️  Tagetik Mapping",       tab1_mapping),
    ("📈  Variance Analysis",     tab2_variance),
    ("🤖  Commentary Generator",  tab3_commentary),
    ("💬  Chat with Data",        tab4_chat),
    ("🗄️  Run History",           tab5_history),
    ("🔍  Comment Search",        tab6_comment_search),
    ("📤  PPT Upload",            tab7_ppt_upload),
]

# ─────────────────────────────────────────────────────────────────────────────
# ONE-TIME SETUP
# ─────────────────────────────────────────────────────────────────────────────
inject_css()
render_header()
render_footer()
init_db()

# ── Session-state defaults ───────────────────────────────────────────────────
_DEFAULTS = {
    "master_df":               None,
    "final_db":                None,
    "leaf_df":                 None,
    "pivot_source_long":       None,
    "var_context":             None,
    "cg_report":               None,
    "cg_trace":                None,
    "analysis_result":         None,
    "current_hierarchy":       None,
    "current_run_id":          None,
    "run_feedback_submitted":  False,
    "chat_history":            [],
    "chat_feedback_submitted": {},
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────────────────────
# RENDER TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_labels  = [label for label, _ in TAB_REGISTRY]
tab_modules = [module for _, module in TAB_REGISTRY]

tabs = st.tabs(tab_labels)

for tab_container, module in zip(tabs, tab_modules):
    with tab_container:
        module.render()
