"""
routers/tab5_history.py
────────────────────────
Tab 5 — Run History (FastAPI router)

Endpoints
---------
GET  /api/tab5/runs            List all runs
GET  /api/tab5/runs/{id}       Get full details for one run
POST /api/tab5/runs/{id}/feedback  Submit thumbs up/down
GET  /api/tab5/summary         Feedback counts overview
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router  = APIRouter()
DB_PATH = Path("analysis_history.db")


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, filename TEXT, hierarchy TEXT,
            total_variance TEXT, summary TEXT, feedback INTEGER DEFAULT 0
        )""")
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN feedback INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit(); conn.close()


_init_db()


# ── GET /api/tab5/runs ───────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs():
    conn = _conn()
    rows = conn.execute(
        "SELECT id, timestamp, filename, total_variance, feedback FROM runs ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    fb_map = {1: "👍", -1: "👎", 0: "➖"}
    return JSONResponse([
        {**dict(r), "feedback_label": fb_map.get(r["feedback"], "➖")}
        for r in rows
    ])


# ── GET /api/tab5/runs/{id} ──────────────────────────────────────────────────

@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    conn = _conn()
    row  = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"Run {run_id} not found.")
    d = dict(row)
    try:
        d["hierarchy_list"] = json.loads(d.get("hierarchy") or "[]")
    except Exception:
        d["hierarchy_list"] = []
    return JSONResponse(d)


# ── POST /api/tab5/runs/{id}/feedback ───────────────────────────────────────

@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: int, request: Request):
    body  = await request.json()
    score = int(body.get("score", 0))   # 1 or -1
    conn  = _conn()
    conn.execute("UPDATE runs SET feedback=? WHERE id=?", (score, run_id))
    conn.commit(); conn.close()
    return JSONResponse({"status": "ok", "run_id": run_id, "score": score})


# ── GET /api/tab5/summary ────────────────────────────────────────────────────

@router.get("/summary")
async def summary():
    conn   = _conn()
    rows   = conn.execute("SELECT feedback FROM runs").fetchall()
    conn.close()
    counts = {"positive": 0, "negative": 0, "none": 0}
    for r in rows:
        f = r["feedback"]
        if f == 1:   counts["positive"] += 1
        elif f == -1: counts["negative"] += 1
        else:         counts["none"]     += 1
    return JSONResponse(counts)
