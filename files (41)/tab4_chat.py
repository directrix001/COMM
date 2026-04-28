"""
routers/tab4_chat.py
─────────────────────
Tab 4 — Chat with Data (FastAPI router)

Endpoints
---------
POST /api/tab4/ask     Send a question → get an answer from the pandas agent
DELETE /api/tab4/clear Clear chat history for this session
"""

from __future__ import annotations

import io
import os
import uuid

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from services import session_store as ss

router = APIRouter()


def _sid(request: Request) -> str:
    return request.cookies.get("va_sid", str(uuid.uuid4()))


def _load_df(sid: str) -> pd.DataFrame:
    """Load best available DataFrame for the session."""
    for key in ["leaf_df_bytes", "master_db_bytes", "final_db_bytes"]:
        raw = ss.get(sid, key)
        if raw:
            return pd.read_json(io.StringIO(raw), orient="split")
    return pd.DataFrame()


# ── POST /api/tab4/ask ───────────────────────────────────────────────────────

@router.post("/ask")
async def ask(request: Request):
    """
    Body JSON: { "question": "What is the total variance for OH?" }
    Returns:   { "answer": "...", "history": [...] }
    """
    sid  = _sid(request)
    body = await request.json()
    question = (body.get("question") or "").strip()

    if not question:
        raise HTTPException(422, "question must not be empty.")

    df = _load_df(sid)
    if df.empty:
        raise HTTPException(404, "No data in session. Upload data in Tab 1 or Tab 2 first.")

    # Load or init chat history
    history: list = ss.get(sid, "chat_history") or []

    # Check Azure env
    endpoint   = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key    = os.getenv("AZURE_OPENAI_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_ver    = os.getenv("AZURE_OPENAI_API_VERSION")

    if not all([endpoint, api_key, deployment, api_ver]):
        answer = (
            "[Azure OpenAI not configured] "
            "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, "
            "AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION in your .env."
        )
    else:
        try:
            answer = await _run_agent(df, question)
        except Exception as exc:
            answer = f"Agent error: {exc}"

    history.append({"role": "user",      "content": question})
    history.append({"role": "assistant", "content": answer})
    ss.set(sid, "chat_history", history)

    return JSONResponse({"answer": answer, "history": history})


# ── DELETE /api/tab4/clear ───────────────────────────────────────────────────

@router.delete("/clear")
async def clear(request: Request):
    sid = _sid(request)
    ss.delete(sid, "chat_history")
    return JSONResponse({"status": "cleared"})


# ── Private ──────────────────────────────────────────────────────────────────

async def _run_agent(df: pd.DataFrame, question: str) -> str:
    import asyncio
    from langchain_openai import AzureChatOpenAI
    from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
    )
    agent = create_pandas_dataframe_agent(
        llm, df, verbose=False,
        agent_type="openai-functions",
        allow_dangerous_code=True,
    )
    # Run in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: agent.invoke({"input": question}))
    return result.get("output", str(result))
