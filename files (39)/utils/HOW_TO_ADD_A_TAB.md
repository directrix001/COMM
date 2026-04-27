# How to Add a New Tab

Adding a new tab to the Variance Analysis Tool takes **3 steps** and touches
**only 2 files**.

---

## Step 1 — Create your tab module

Create a file at `tabs/tab6_myfeature.py` (use the next number in sequence).

The only requirement is a top-level `render()` function:

```python
# tabs/tab6_myfeature.py

import streamlit as st

def render() -> None:
    """Everything you want to show in the tab goes here."""
    st.markdown('<p class="va-section-label">🚀 My New Feature</p>', unsafe_allow_html=True)
    st.write("Hello from tab 6!")
```

You can import and use anything from the `utils/` package:

```python
from utils.data_helpers  import cached_read_and_normalise, get_filter_options
from utils.formatting    import fmt_num, fmt_pct
from utils.html_builders import build_pivot_html
from utils.database      import fetch_run_history
from utils.ai_engine     import azure_env_ok, build_graph
```

---

## Step 2 — Register the tab in `app.py`

Open `app.py` and add one line to `TAB_REGISTRY`:

```python
from tabs import tab6_myfeature          # ← add this import

TAB_REGISTRY = [
    ("🗂️  Tagetik Mapping",      tab1_mapping),
    ("📈  Variance Analysis",    tab2_variance),
    ("🤖  Commentary Generator", tab3_commentary),
    ("💬  Chat with Data",       tab4_chat),
    ("🗄️  Run History",          tab5_history),
    ("🚀  My New Feature",       tab6_myfeature),   # ← add this line
]
```

---

## Step 3 — Run the app

```bash
streamlit run app.py
```

Your new tab appears automatically. No other file needs changing.

---

## Project structure

```
variance_app/
│
├── app.py                     ← Main entry point & TAB_REGISTRY
│
├── tabs/                      ← One file per tab
│   ├── __init__.py
│   ├── tab1_mapping.py        Tab 1 — Tagetik Mapping
│   ├── tab2_variance.py       Tab 2 — Variance Analysis
│   ├── tab3_commentary.py     Tab 3 — AI Commentary Generator
│   ├── tab4_chat.py           Tab 4 — Chat with Data
│   └── tab5_history.py        Tab 5 — Run History
│
└── utils/                     ← Shared utilities (never import from tabs/)
    ├── __init__.py
    ├── constants.py           Month maps, column ordering, path constants
    ├── formatting.py          fmt_num, fmt_pct, variance_color_class
    ├── data_helpers.py        Cached read / filter / pivot helpers
    ├── database.py            SQLite init, save, fetch, feedback callbacks
    ├── styles.py              CSS injection, header, footer
    ├── html_builders.py       Pivot table HTML, hotspot cards HTML
    ├── excel_export.py        Multi-sheet .xlsx builder
    └── ai_engine.py           LangGraph agent, PPTX generator, Azure check
```

---

## Shared session-state keys

All session-state keys are initialised in `app.py`. Tab modules read and
write them directly via `st.session_state`.

| Key | Set by | Read by |
|-----|--------|---------|
| `final_db` | Tab 1 | Tab 2, Tab 4 |
| `master_df` | Tab 2 | Tab 2 |
| `leaf_df` | Tab 2 | Tab 3, Tab 4 |
| `pivot_source_long` | Tab 2 | Tab 2 (export) |
| `var_context` | Tab 2 | Tab 3 |
| `analysis_result` | Tab 3 | Tab 3 |
| `cg_report` / `cg_trace` | Tab 3 | Tab 3 |
| `current_run_id` | Tab 3 | Tab 3 |
| `run_feedback_submitted` | Tab 3 | Tab 3 |
| `chat_history` | Tab 4 | Tab 4 |
| `chat_feedback_submitted` | Tab 4 | Tab 4 |
