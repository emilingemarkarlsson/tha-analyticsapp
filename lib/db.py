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


@st.cache_data(ttl=3600, show_spinner=False)
def get_data_date() -> str:
    """Return the most recent game date available in the database.
    Cached 1 h — used by every page header for trust/freshness signal.
    """
    try:
        row = get_con().execute(
            "SELECT MAX(game_date)::VARCHAR AS d FROM games WHERE game_type = 2"
        ).fetchone()
        if row and row[0]:
            return str(row[0])[:10]
    except Exception:
        pass
    return "—"


@st.cache_data(ttl=3600, show_spinner=False)
def player_career(player_id: str) -> pd.DataFrame:
    """Season-by-season career stats for one player. Cached 1 h.
    Heavy query (joins player_game_stats × games across 16 seasons).
    """
    return get_con().execute(f"""
        SELECT g.season,
               COUNT(DISTINCT pgs.game_id)        AS gp,
               SUM(pgs.goals)                     AS goals,
               SUM(pgs.assists)                   AS assists,
               SUM(pgs.goals + pgs.assists)       AS points,
               SUM(pgs.toi_seconds) / 3600.0      AS toi_hours,
               AVG(pgs.toi_seconds) / 60.0        AS avg_toi_min
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.game_id
        WHERE TRY_CAST(pgs.player_id AS VARCHAR) = '{player_id}'
          AND g.game_type = 2
          AND pgs.toi_seconds > 0
        GROUP BY g.season
        HAVING COUNT(DISTINCT pgs.game_id) >= 5
        ORDER BY g.season
    """).df()


@st.cache_data(ttl=3600, show_spinner=False)
def team_career(team_abbr: str) -> pd.DataFrame:
    """Season-by-season franchise history from standings. Cached 1 h."""
    return get_con().execute(f"""
        SELECT season,
               wins, losses, otLosses, gamesPlayed,
               points, goalFor, goalAgainst, goalDifferential,
               winPctg, pointPctg, divisionName
        FROM standings
        WHERE teamAbbrev = '{team_abbr}'
        ORDER BY season
    """).df()
