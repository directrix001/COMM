"""
tabs/tab4_chat.py
─────────────────
Tab 4 — Chat with Data

Natural-language Q&A over the loaded dataset using
Azure OpenAI + LangChain pandas agent.

Public API
----------
render()   — call inside  `with tab4:` in app.py
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.ai_engine import azure_env_ok
from utils.database import handle_chat_feedback_click, save_chat


def render() -> None:
    st.markdown('<p class="va-section-label">💬 Chat with Your Data</p>', unsafe_allow_html=True)
    st.markdown(
        "Ask natural language questions about your loaded dataset using Azure OpenAI + LangChain."
    )

    chat_df, chat_source_label = _resolve_data_source()
    chat_df = _optional_upload_override(chat_df)

    if chat_df is not None and not azure_env_ok():
        st.warning("⚠️ Azure OpenAI credentials not set — chat is disabled. Configure .env and restart.")
        return

    if chat_df is None:
        st.info("Load a data source above to start chatting.")
        return

    _render_chat(chat_df)


# ─── Private helpers ─────────────────────────────────────────────────────────

def _resolve_data_source():
    """Return (df, label) from session_state if available."""
    chat_df            = None
    chat_source_label  = ""

    if st.session_state.get("leaf_df") is not None:
        chat_source_label = "Tab 2 Pivot Data"
        chat_df           = st.session_state.leaf_df
    elif st.session_state.get("final_db") is not None:
        chat_source_label = "Tab 1 Mapping Output"
        chat_df           = st.session_state.final_db

    col_src, _ = st.columns([2, 2])
    with col_src:
        if chat_df is not None:
            st.markdown(
                f'<div class="cg-status-ok">✅ Chatting with: <strong>{chat_source_label}</strong>'
                f" — {len(chat_df):,} rows</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="cg-status-warn">ℹ️ No data loaded yet. '
                "Upload below or run Variance Analysis first.</div>",
                unsafe_allow_html=True,
            )

    return chat_df, chat_source_label


def _optional_upload_override(chat_df):
    """Render the optional upload widget; returns overriding df or original."""
    _, col_upload = st.columns([2, 2])
    with col_upload:
        chat_upload = st.file_uploader(
            "Or upload a separate file to chat with",
            type=["csv", "xlsx", "xls"],
            key="chat_upload",
        )
        if chat_upload:
            try:
                if chat_upload.name.endswith(".csv"):
                    chat_df = pd.read_csv(chat_upload)
                else:
                    raw = chat_upload.getvalue()
                    xls = pd.ExcelFile(io.BytesIO(raw))
                    sheet = (
                        st.selectbox("Select sheet", xls.sheet_names, key="chat_sheet")
                        if len(xls.sheet_names) > 1
                        else xls.sheet_names[0]
                    )
                    chat_df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, engine="openpyxl")
                st.success(f"✅ Uploaded — {len(chat_df):,} rows")
            except Exception as e:
                st.error(f"Upload error: {e}")
    return chat_df


def _render_chat(chat_df: pd.DataFrame) -> None:
    """Render message history, chat input, and feedback buttons."""
    chat_history = st.session_state.setdefault("chat_history", [])

    for idx, msg in enumerate(chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and "db_id" in msg:
                if st.session_state.get("chat_feedback_submitted", {}).get(idx):
                    st.success("Feedback recorded ✅")
                else:
                    f1, f2, _ = st.columns([1, 1, 10])
                    f1.button(
                        "👍", key=f"chat_up_{idx}",
                        on_click=handle_chat_feedback_click,
                        args=(msg["db_id"], 1, idx),
                    )
                    f2.button(
                        "👎", key=f"chat_down_{idx}",
                        on_click=handle_chat_feedback_click,
                        args=(msg["db_id"], -1, idx),
                    )

    if prompt := st.chat_input("Ask your dataset a question…"):
        chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
                from langchain_experimental.agents.agent_toolkits import (
                    create_pandas_dataframe_agent,
                )
                from langchain_openai import AzureChatOpenAI
                import os

                llm_chat = AzureChatOpenAI(
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=os.getenv("AZURE_OPENAI_KEY"),
                    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                    temperature=0,
                )
                st_callback = StreamlitCallbackHandler(st.container())
                agent = create_pandas_dataframe_agent(
                    llm_chat, chat_df, verbose=True,
                    agent_type="openai-functions",
                    allow_dangerous_code=True,
                )
                response = agent.invoke({"input": prompt}, {"callbacks": [st_callback]})
                answer   = response["output"]
                st.markdown(answer)

                chat_id = save_chat(prompt, answer)
                chat_history.append({"role": "assistant", "content": answer, "db_id": chat_id})
                st.rerun()

            except Exception as e:
                st.error(f"Chat error: {e}")

    if chat_history:
        if st.button("🗑️ Clear Chat History", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.chat_feedback_submitted = {}
            st.rerun()
