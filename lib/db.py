"""MotherDuck connection – cached per session."""
import os
import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource(show_spinner=False)
def get_con() -> duckdb.DuckDBPyConnection:
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN not set")
    return duckdb.connect(
        f"md:nhl?motherduck_token={token}&attach_mode=single"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    """Run a SQL query and return a DataFrame. Results cached 1 h."""
    return get_con().execute(sql).df()


def query_fresh(sql: str) -> pd.DataFrame:
    """Run a SQL query without caching (for chat/interactive use)."""
    return get_con().execute(sql).df()
