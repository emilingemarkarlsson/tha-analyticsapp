"""AI Chat – Text-to-SQL via LiteLLM."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query_fresh
from lib.litellm_client import text_to_sql, fix_sql, summarise

st.set_page_config(page_title="AI Chat – THA Analytics", layout="wide")

st.markdown(
    "<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;margin-bottom:4px;'>AI Chat</h1>"
    "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>Ask anything about NHL data — 16 seasons, 850K+ game records</p>",
    unsafe_allow_html=True,
)

EXAMPLES = [
    "Who has the most points in the last 5 games?",
    "Show me Toronto's last 10 games",
    "Which goalies have the best save% this season?",
    "Top scorers in the 2024-25 season",
    "Which teams have the best home record this season?",
]

# Example chips
st.markdown("<p style='font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Try these</p>", unsafe_allow_html=True)
cols = st.columns(len(EXAMPLES))
clicked = None
for i, ex in enumerate(EXAMPLES):
    with cols[i]:
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            clicked = ex

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            st.markdown(msg["content"])
            if "df" in msg:
                df: pd.DataFrame = msg["df"]
                if not df.empty:
                    st.markdown(
                        f"<p style='color:#8896a8;font-size:11px;margin-bottom:4px;'>{len(df)} rows returned</p>",
                        unsafe_allow_html=True,
                    )
                    st.dataframe(df, use_container_width=True, hide_index=True)
            if "sql" in msg:
                with st.expander("Show SQL"):
                    st.code(msg["sql"], language="sql")
        else:
            st.markdown(msg["content"])

# Input
question = st.chat_input("Ask a question about NHL data...") or clicked

def validate_sql(sql: str) -> tuple[bool, str]:
    norm = sql.strip().upper()
    if not norm.startswith("SELECT"):
        return False, "Only SELECT queries allowed."
    if "LIMIT" not in norm:
        return False, "Query must include LIMIT."
    return True, ""

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL..."):
            try:
                sql = text_to_sql(question)
            except Exception as e:
                st.error(f"LiteLLM error: {e}")
                st.stop()

        ok, err = validate_sql(sql)
        if not ok:
            st.error(f"Invalid SQL: {err}")
            st.stop()

        with st.spinner("Running query..."):
            try:
                df = query_fresh(sql)
            except Exception as exec_err:
                with st.spinner("Fixing SQL..."):
                    try:
                        sql = fix_sql(question, sql, str(exec_err))
                        ok2, err2 = validate_sql(sql)
                        if not ok2:
                            st.error(f"Could not fix query: {err2}")
                            st.stop()
                        df = query_fresh(sql)
                    except Exception as e2:
                        st.error(f"Query failed: {e2}")
                        st.stop()

        summary = ""
        if not df.empty:
            with st.spinner("Summarising..."):
                try:
                    summary = summarise(question, df.head(10).to_dict("records"))
                except Exception:
                    summary = f"{len(df)} rows returned."

        reply = summary or f"{len(df)} rows returned."
        st.markdown(reply)

        if not df.empty:
            st.markdown(
                f"<p style='color:#8896a8;font-size:11px;margin-bottom:4px;'>{len(df)} rows</p>",
                unsafe_allow_html=True,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Show SQL"):
            st.code(sql, language="sql")

        st.session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "df": df,
            "sql": sql,
        })
