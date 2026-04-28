# Variance Analysis Tool — FastAPI + Bootstrap

## Project Structure

```
fastapi_app/
│
├── main.py                         ← FastAPI app entry point
├── requirements.txt                ← Python dependencies
├── .env.example                    ← Copy to .env and fill in Azure keys
│
├── routers/                        ← One router per tab (API endpoints)
│   ├── __init__.py
│   ├── tab1_mapping.py             POST /api/tab1/upload, GET /api/tab1/download/*
│   ├── tab2_variance.py            POST /api/tab2/upload|upload-two|run, GET /api/tab2/download/xlsx
│   ├── tab3_commentary.py          POST /api/tab3/run, GET /api/tab3/download/*
│   ├── tab4_chat.py                POST /api/tab4/ask, DELETE /api/tab4/clear
│   ├── tab5_history.py             GET /api/tab5/runs, POST /api/tab5/runs/{id}/feedback
│   ├── tab6_search.py              GET /api/tab6/filters, POST /api/tab6/search, GET /api/tab6/download/*
│   └── tab7_ppt.py                 POST /api/tab7/upload|push, GET /api/tab7/download|master
│
├── services/                       ← Pure Python business logic (no framework dependency)
│   ├── __init__.py
│   ├── data_helpers.py             Excel read, normalise, filter, pivot, variance
│   ├── excel_export.py             Multi-sheet .xlsx builder
│   └── session_store.py            In-memory session state (replace with Redis for prod)
│
├── templates/
│   └── index.html                  ← Single-page app shell (Bootstrap 5)
│
└── static/
    ├── css/
    │   └── app.css                 ← Full brand CSS (dark header, light body)
    └── js/
        ├── core.js                 ← Tab switching, toast, multiselect, API helpers
        ├── tab1.js                 ← Tagetik Mapping UI logic
        ├── tab2.js                 ← Variance Analysis UI logic
        ├── tab3.js                 ← Commentary Generator UI logic
        ├── tab4.js                 ← Chat with Data UI logic
        └── tab5.js                 ← Run History UI logic
```

## Build Status

| Tab | Router | JS | Status |
|-----|--------|----|--------|
| 1 — Tagetik Mapping       | ✅ tab1_mapping.py    | ✅ tab1.js | **Fully working** |
| 2 — Variance Analysis     | ✅ tab2_variance.py   | ✅ tab2.js | **Fully working** |
| 3 — Commentary Generator  | ✅ tab3_commentary.py | ✅ tab3.js | Working (needs Azure keys) |
| 4 — Chat with Data        | ✅ tab4_chat.py       | ✅ tab4.js | Working (needs Azure keys) |
| 5 — Run History           | ✅ tab5_history.py    | ✅ tab5.js | **Fully working** |
| 6 — Comment Search        | ✅ tab6_search.py     | Placeholder | Next build |
| 7 — PPT Upload            | ✅ tab7_ppt.py        | Placeholder | Next build |

## How to Run

### 1. Clone / copy files into a folder

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

### 5. Create required folders
```bash
mkdir -p backend database
# Place mapping.xlsx inside backend/ for Tab 1 enrichment (optional)
```

### 6. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 7. Open browser
```
http://localhost:8000
```

### API Docs (auto-generated)
```
http://localhost:8000/docs
```

## Adding a New Tab

1. Create `routers/tab8_myfeature.py` with a FastAPI `APIRouter`
2. Create `static/js/tab8.js` with an `init()` function triggered by `va:tabchange`
3. In `main.py`, import and register: `app.include_router(tab8_myfeature.router, prefix="/api/tab8")`
4. In `templates/index.html`, add the tab button, panel div, and script tag

## Session Management

Sessions are stored in-memory (dict) via `services/session_store.py`.
For production, replace with Redis using `aioredis` or a DB-backed store.
Session ID is stored in a browser cookie (`va_sid`).
