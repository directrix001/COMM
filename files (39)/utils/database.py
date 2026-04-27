"""
utils/database.py
─────────────────
SQLite helpers — initialisation, save/update/fetch for
run history and chat logs.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

DB_PATH = "analysis_history.db"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS runs
           (id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, filename TEXT, hierarchy TEXT,
            total_variance TEXT, summary TEXT, feedback INTEGER DEFAULT 0)"""
    )
    try:
        c.execute("ALTER TABLE runs ADD COLUMN feedback INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    c.execute(
        """CREATE TABLE IF NOT EXISTS chat_logs
           (id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, prompt TEXT, response TEXT, feedback INTEGER DEFAULT 0)"""
    )
    conn.commit()
    conn.close()


def save_run(filename: str, hierarchy: List[str], total_variance: str, summary: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO runs (timestamp, filename, hierarchy, total_variance, summary) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, json.dumps(hierarchy), total_variance, summary),
    )
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id


def update_run_feedback(run_id: int, feedback: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE runs SET feedback = ? WHERE id = ?", (feedback, run_id))
    conn.commit()
    conn.close()


def save_chat(prompt: str, response: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_logs (timestamp, prompt, response) VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), prompt, response),
    )
    chat_id = c.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def update_chat_feedback(chat_id: int, feedback: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE chat_logs SET feedback = ? WHERE id = ?", (feedback, chat_id))
    conn.commit()
    conn.close()


def fetch_run_history() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM runs ORDER BY timestamp DESC", conn)
    conn.close()
    return df


# ─── Feedback callbacks (called by Streamlit on_click) ───────────────────────

def handle_run_feedback_click(run_id: int, score: int) -> None:
    update_run_feedback(run_id, score)
    st.session_state.run_feedback_submitted = True
    st.toast("✅ Analysis feedback recorded!")


def handle_chat_feedback_click(chat_id: int, score: int, msg_idx: int) -> None:
    update_chat_feedback(chat_id, score)
    st.session_state.chat_feedback_submitted[msg_idx] = True
    st.toast("✅ Chat feedback recorded!")
