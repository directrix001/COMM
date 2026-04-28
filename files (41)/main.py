"""
main.py — FastAPI entry point
==============================
Run:  uvicorn main:app --reload --port 8000
Then open:  http://localhost:8000
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

from routers import (
    tab1_mapping, tab2_variance, tab3_commentary,
    tab4_chat, tab5_history, tab6_comment_search, tab7_ppt_upload,
)

app = FastAPI(title="Variance Analysis Tool", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(tab1_mapping.router,        prefix="/api/tab1", tags=["Tagetik Mapping"])
app.include_router(tab2_variance.router,       prefix="/api/tab2", tags=["Variance Analysis"])
app.include_router(tab3_commentary.router,     prefix="/api/tab3", tags=["Commentary Generator"])
app.include_router(tab4_chat.router,           prefix="/api/tab4", tags=["Chat with Data"])
app.include_router(tab5_history.router,        prefix="/api/tab5", tags=["Run History"])
app.include_router(tab6_comment_search.router, prefix="/api/tab6", tags=["Comment Search"])
app.include_router(tab7_ppt_upload.router,     prefix="/api/tab7", tags=["PPT Upload"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_fallback(request: Request, full_path: str = ""):
    if full_path.startswith(("api/", "static/")):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("index.html", {"request": request})
