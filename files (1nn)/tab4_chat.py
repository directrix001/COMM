"""
routers/tab4_chat.py  — UPDATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tab 4 — Chat with Data

WHAT CHANGED vs previous version
─────────────────────────────────
1. Agent logic replaced with the full pattern from the uploaded agent script:
   - build_system_prompt()     → detailed system prompt with A/B/C answer rules
   - build_agent()             → create_pandas_dataframe_agent with full config
                                  (tool-calling, number_of_head_rows, include_df_in_prompt,
                                   max_iterations, prefix=system_prompt)
   - _build_input()            → prepends conversation history as plain text
                                  so the agent sees prior Q&A turns
   - ask_with_memory()         → wraps agent.invoke() + saves turn to session

2. TWO DATA SOURCE MODES — controlled by body.data_source:
   - "tab1" → uses final_db_bytes  (Tagetik Mapping output, Tab 1)
              DataFrame: the merged/enriched mapping DataFrame with
              Entity_desc, Region, Market, CostCat description, OH/LC,
              MTD, YTD, and all month columns (1-Apr … 12-Mar)
   - "tab2" → uses leaf_df_bytes   (Variance pivot result, Tab 2)
              DataFrame: the pivot with scenario columns, Variance (M€),
              Variance %, and all group_fields (OH/LC, Division_Desc …)
   Falls back to master_db_bytes if specific key is missing.

3. Conversation memory per (session_id + data_source) pair — switching
   data source resets context so answers don't bleed across datasets.

4. env var name aligned: AZURE_OPENAI_KEY (was AZURE_OPENAI_API_KEY
   in the uploaded script — kept as AZURE_OPENAI_KEY to match .env.example).

Endpoints
─────────
POST /api/tab4/ask     {question, data_source: "tab1"|"tab2"}
GET  /api/tab4/status  Returns which data sources are loaded in session
DELETE /api/tab4/clear Clear chat history for current session
"""

from __future__ import annotations

import asyncio
import io
import os
import uuid
from collections import deque

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from services import session_store as ss

router = APIRouter()

# ── Max conversation turns kept in memory (matches uploaded script default) ──
MAX_TURNS = 10


# ════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ── Ported directly from build_system_prompt() in the uploaded agent script ──
# ════════════════════════════════════════════════════════════════════════════

def _build_system_prompt() -> str:
    """
    System prompt from the uploaded CSV/Excel Database Agent script.
    Instructs the pandas agent how to handle:
      A. Normal dataframe queries
      B. User-provided literal numbers (use conversation history as base)
      C. Follow-up questions without a number
    """
    return """You are a data analyst assistant. The dataset is loaded into a pandas DataFrame called `df`.

HOW TO ANSWER:

A. QUERY THE DATAFRAME (default):
   For questions about data, aggregations, filters, trends, or comparisons where
   both values come from `df` — write and run the correct pandas code.

B. USER PROVIDES A LITERAL NUMBER:
   If the user states an explicit number in their message (e.g. "actual is 456896556"),
   treat it as given — do NOT re-query `df` for it.
   Use the prior answer from conversation history as the base value.
   Show: absolute difference AND % change, with the two numbers used.

C. FOLLOW-UP WITHOUT A NUMBER:
   If the user asks a follow-up without stating a number, query `df` normally.

ALWAYS:
- Check `df.columns` and `df[col].unique()` before filtering to use exact column names AND exact values.
- Special characters in values (e.g. +, /, -, spaces) must match exactly as they appear in the data.
- For comparison questions, query each value separately then compute difference and % change.
- Lead with the result, then show the working.
- Format large numbers with commas (e.g. 1,234,567).
- State any assumptions if the question is ambiguous.
- Output plain text only — no LaTeX, no markdown math (no [ ], fractions, or math notation), no asterisks for bold.
- Show calculations as simple plain text: e.g.  386,929,148 - 385,748,395 = 1,180,753"""


# ════════════════════════════════════════════════════════════════════════════
# DATA SOURCE LOADER
# ════════════════════════════════════════════════════════════════════════════

def _load_df(sid: str, data_source: str) -> pd.DataFrame:
    """
    Load the correct DataFrame based on data_source radio button selection.

    data_source = "tab1"
        → final_db_bytes  (Tab 1 Tagetik Mapping output)
          DataFrame contains: Entity_desc, Region, Market, OH/LC,
          CostCat description, Division_Desc, Function_Desc,
          MTD, YTD, 1-Apr … 12-Mar month columns, Scenario
          This is the FULL enriched dataset before scenario filtering.

    data_source = "tab2"
        → leaf_df_bytes   (Tab 2 Variance Analysis pivot result)
          DataFrame contains: group_fields (e.g. OH/LC, Division_Desc),
          <Scenario A name>, <Scenario B name>,
          Variance (M€), Variance %
          This is the AGGREGATED pivot — fewer rows, pre-computed variance.

    Falls back to master_db_bytes (Tab 2 uploaded master) if leaf missing.
    Final fallback: any available session data.
    """
    # ── Tab 1: Tagetik Mapping output ────────────────────────────────────────
    if data_source == "tab1":
        raw = ss.get(sid, "final_db_bytes")
        if raw:
            return pd.read_json(io.StringIO(raw), orient="split")
        # warn caller — no Tab 1 data
        return pd.DataFrame()

    # ── Tab 2: Variance pivot result (preferred) or master DB ────────────────
    if data_source == "tab2":
        # First try the pivot result (leaf_df — has Variance M€ and Variance %)
        raw = ss.get(sid, "leaf_df_bytes")
        if raw:
            return pd.read_json(io.StringIO(raw), orient="split")
        # Fall back to full master DB (has Scenario column, pre-pivot)
        raw = ss.get(sid, "master_db_bytes")
        if raw:
            return pd.read_json(io.StringIO(raw), orient="split")
        return pd.DataFrame()

    # ── Unknown source: try everything ───────────────────────────────────────
    for key in ["leaf_df_bytes", "master_db_bytes", "final_db_bytes"]:
        raw = ss.get(sid, key)
        if raw:
            return pd.read_json(io.StringIO(raw), orient="split")
    return pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# CONVERSATION MEMORY  (ported from the uploaded script)
# Key: (sid, data_source) — switching dataset resets context
# ════════════════════════════════════════════════════════════════════════════

def _mem_key(sid: str, data_source: str) -> str:
    """
    Conversation history is stored per (session, data_source) pair.
    Switching between Tab 1 and Tab 2 gives a fresh conversation context
    so answers from one dataset don't bleed into the other.
    """
    return f"chat_history__{data_source}"


def _get_history(sid: str, data_source: str) -> list:
    """
    Retrieve conversation history for this (session, data_source).
    Returns list of dicts: [{role, content}, …]
    """
    key = _mem_key(sid, data_source)
    return ss.get(sid, key) or []


def _save_turn(sid: str, data_source: str, question: str, answer: str) -> list:
    """
    Append a Q&A turn to conversation history, capped at MAX_TURNS pairs.
    """
    key     = _mem_key(sid, data_source)
    history = ss.get(sid, key) or []
    history.append({"role": "user",      "content": question})
    history.append({"role": "assistant", "content": answer})
    # Keep only last MAX_TURNS * 2 messages (each turn = 2 messages)
    if len(history) > MAX_TURNS * 2:
        history = history[-(MAX_TURNS * 2):]
    ss.set(sid, key, history)
    return history


def _build_input_with_history(question: str, history: list) -> str:
    """
    Ported from _build_input() in the uploaded script.
    Prepends conversation history as plain text so the agent
    understands follow-up questions and can reference prior answers.
    """
    if not history:
        return question

    history_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in history
    ])
    return (
        f"Conversation so far:\n"
        f"{history_text}\n\n"
        f"Current question: {question}"
    )


# ════════════════════════════════════════════════════════════════════════════
# AGENT BUILDER  (ported from build_agent() in the uploaded script)
# ════════════════════════════════════════════════════════════════════════════

def _build_agent(df: pd.DataFrame):
    """
    Build the pandas dataframe agent using the full configuration
    from the uploaded CSV/Excel Database Agent script.

    Key differences from the old simple agent:
    - agent_type="tool-calling"   (was "openai-functions")
    - number_of_head_rows=10      (shows agent more context rows)
    - include_df_in_prompt=True   (agent sees column names in system)
    - max_iterations=20           (allows complex multi-step queries)
    - prefix=system_prompt        (the detailed A/B/C instruction set)
    - verbose=False               (suppress intermediate steps in logs)
    """
    from langchain_openai import AzureChatOpenAI
    from langchain_experimental.agents import create_pandas_dataframe_agent

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
    )

    # ── create_pandas_dataframe_agent with full config from uploaded script ──
    agent = create_pandas_dataframe_agent(
        llm=llm,
        df=df,
        agent_type="tool-calling",          # matches uploaded script
        verbose=False,
        allow_dangerous_code=True,
        number_of_head_rows=10,             # agent sees 10 head rows for context
        include_df_in_prompt=True,          # column names in system prompt
        max_iterations=20,                  # allow multi-step reasoning
        prefix=_build_system_prompt(),      # detailed A/B/C instruction set
    )
    return agent


async def _run_agent_with_memory(
    df: pd.DataFrame,
    question: str,
    history: list,
) -> str:
    """
    Ported from ask() in the uploaded script.
    Builds the full input (history + question) then invokes the agent
    in a thread pool executor to avoid blocking FastAPI's async event loop.
    """
    full_input = _build_input_with_history(question, history)
    agent      = _build_agent(df)

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: agent.invoke({"input": full_input})
    )
    return result.get("output", str(result))


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

def _sid(request: Request) -> str:
    return request.cookies.get("va_sid", str(uuid.uuid4()))


# ── POST /api/tab4/ask ───────────────────────────────────────────────────────

@router.post("/ask")
async def ask(request: Request):
    """
    Body JSON:
    {
      "question":    "What is the total Variance (M€)?",
      "data_source": "tab1" | "tab2"        ← NEW: radio button selection
    }

    data_source="tab1" → chats with Tagetik Mapping DataFrame
                         (final_db_bytes: enriched, all months, all entities)
    data_source="tab2" → chats with Variance Analysis pivot
                         (leaf_df_bytes: Variance M€, Variance %, scenario cols)

    Returns: { "answer": "...", "history": [...], "data_source": "tab2" }
    """
    sid  = _sid(request)
    body = await request.json()

    question    = (body.get("question")    or "").strip()
    data_source = (body.get("data_source") or "tab2").strip()  # default: variance data

    if not question:
        raise HTTPException(422, "question must not be empty.")

    # ── Load correct DataFrame based on radio button selection ───────────────
    df = _load_df(sid, data_source)

    if df.empty:
        # Return a descriptive error message — not a 500 crash
        source_name = (
            "Tagetik Mapping (Tab 1)" if data_source == "tab1"
            else "Variance Analysis (Tab 2)"
        )
        raise HTTPException(
            404,
            f"No {source_name} data found in session. "
            f"Please run {'Tab 1 Mapping' if data_source == 'tab1' else 'Tab 2 Variance Analysis'} first."
        )

    # ── Check Azure env vars ─────────────────────────────────────────────────
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
        history = _get_history(sid, data_source)
        history = _save_turn(sid, data_source, question, answer)
        return JSONResponse({"answer": answer, "history": history, "data_source": data_source})

    # ── Get conversation history for this (session, data_source) pair ────────
    history = _get_history(sid, data_source)

    try:
        # ── Invoke agent with memory (ported from uploaded script's ask()) ───
        answer = await _run_agent_with_memory(df, question, history)
    except Exception as exc:
        answer = f"Agent error: {exc}"

    # ── Save turn to conversation memory ─────────────────────────────────────
    updated_history = _save_turn(sid, data_source, question, answer)

    return JSONResponse({
        "answer":      answer,
        "history":     updated_history,
        "data_source": data_source,
    })


# ── GET /api/tab4/status ─────────────────────────────────────────────────────

@router.get("/status")
async def status(request: Request):
    """
    Returns which data sources are available in session.
    Frontend uses this to show/disable radio buttons and show warnings.
    """
    sid = _sid(request)
    return JSONResponse({
        "tab1_available": ss.get(sid, "final_db_bytes")  is not None,
        "tab2_available": (
            ss.get(sid, "leaf_df_bytes")   is not None or
            ss.get(sid, "master_db_bytes") is not None
        ),
    })


# ── DELETE /api/tab4/clear ───────────────────────────────────────────────────

@router.delete("/clear")
async def clear(request: Request):
    """Clear chat history for both data sources in current session."""
    sid = _sid(request)
    ss.delete(sid, "chat_history__tab1")
    ss.delete(sid, "chat_history__tab2")
    return JSONResponse({"status": "cleared"})
