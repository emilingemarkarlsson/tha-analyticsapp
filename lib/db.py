"""MotherDuck connection – cached per league."""
import os
import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DB_MAP: dict[str, str] = {"nhl": "nhl"}
LEAGUE_LABELS: dict[str, str] = {"nhl": "NHL"}


@st.cache_resource(show_spinner=False)
def get_con(league: str = "nhl") -> duckdb.DuckDBPyConnection:
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN not set")
    db_name = DB_MAP.get(league, "nhl")
    return duckdb.connect(
        f"md:{db_name}?motherduck_token={token}&attach_mode=single"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def query(sql: str, league: str = "nhl") -> pd.DataFrame:
    """Run a SQL query and return a DataFrame. Results cached 1 h."""
    return get_con(league).execute(sql).df()


def query_fresh(sql: str, league: str = "nhl") -> pd.DataFrame:
    """Run a SQL query without caching (for chat/interactive use)."""
    return get_con(league).execute(sql).df()


@st.cache_data(ttl=3600, show_spinner=False)
def get_data_date(league: str = "nhl") -> str:
    """Return the most recent data date for the NHL database."""
    try:
        row = get_con("nhl").execute(
            "SELECT MAX(game_date)::VARCHAR AS d FROM player_game_stats"
            " WHERE CAST((game_id / 10000) % 100 AS INTEGER) = 2"
        ).fetchone()
        if row and row[0]:
            return str(row[0])[:10]
    except Exception:
        pass
    return "—"


@st.cache_data(ttl=3600, show_spinner=False)
def player_career(player_id: str) -> pd.DataFrame:
    """Season-by-season NHL career stats for one player. Cached 1 h."""
    return get_con("nhl").execute(f"""
        SELECT CAST(game_id / 1000000 AS INTEGER) * 10000
                 + CAST(game_id / 1000000 AS INTEGER) + 1   AS season,
               COUNT(DISTINCT game_id)                      AS gp,
               SUM(goals)                                   AS goals,
               SUM(assists)                                 AS assists,
               SUM(points)                                  AS points,
               SUM(toi_seconds) / 3600.0                   AS toi_hours,
               AVG(toi_seconds) / 60.0                     AS avg_toi_min
        FROM player_game_stats
        WHERE TRY_CAST(player_id AS VARCHAR) = '{player_id}'
          AND CAST((game_id / 10000) % 100 AS INTEGER) = 2
          AND toi_seconds > 0
        GROUP BY 1
        HAVING COUNT(DISTINCT game_id) >= 5
        ORDER BY 1
    """).df()


@st.cache_data(ttl=3600, show_spinner=False)
def team_career(team_abbr: str) -> pd.DataFrame:
    """Season-by-season NHL franchise history from standings. Cached 1 h."""
    return get_con("nhl").execute(f"""
        SELECT season,
               wins, losses, otLosses, gamesPlayed,
               points, goalFor, goalAgainst, goalDifferential,
               winPctg, pointPctg, divisionName
        FROM standings
        WHERE teamAbbrev = '{team_abbr}'
        ORDER BY season
    """).df()


@st.cache_data(ttl=3600, show_spinner=False)
def get_standings(league: str = "nhl", season=None) -> pd.DataFrame:
    """Return NHL standings for the given season."""
    con = get_con("nhl")
    try:
        if True:
            s = f"season = {season}" if season else "season = (SELECT MAX(season) FROM standings)"
            return con.execute(f"""
                SELECT teamAbbrev AS team, wins, losses, otLosses AS otl,
                       gamesPlayed AS gp, points AS pts,
                       goalFor AS gf, goalAgainst AS ga,
                       (CAST(goalFor AS INTEGER) - CAST(goalAgainst AS INTEGER)) AS diff,
                       divisionAbbrev AS division
                FROM standings
                WHERE {s}
                ORDER BY pts DESC
            """).df()
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_scorers(league: str = "nhl", season=None, limit: int = 20) -> pd.DataFrame:
    """Return NHL top scorers for the current season."""
    try:
        return get_con("nhl").execute(f"""
            SELECT player_first_name || ' ' || player_last_name AS player,
                   team_abbr AS team,
                   SUM(goals) AS goals, SUM(assists) AS assists, SUM(points) AS points,
                   COUNT(DISTINCT pgs.game_id) AS gp
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.game_id
            WHERE g.game_type = '2'
              AND g.season = (SELECT MAX(season) FROM games WHERE game_type = '2')
            GROUP BY 1, 2
            ORDER BY points DESC
            LIMIT {limit}
        """).df()
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_league_seasons(league: str = "nhl") -> list:
    """Return available NHL seasons, newest first."""
    try:
        rows = get_con("nhl").execute(
            "SELECT DISTINCT season FROM games WHERE game_type = '2' ORDER BY season DESC"
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []
