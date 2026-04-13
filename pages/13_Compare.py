"""Head-to-head comparison page – Players & Teams."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px

from lib.db import query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, empty_state, inline_error, data_source_footer

st.set_page_config(
    page_title="Compare – THA Analytics",
    page_icon="tha_icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
_render_sidebar()
require_login()
page_header("Compare", "Head-to-head · Players & Teams", data_date=get_data_date())

# ── Design tokens ───────────────────────────────────────────────────────────────
GREEN  = "#5a8f4e"
MUTED  = "#8896a8"
ORANGE = "#f97316"
BLUE   = "#87ceeb"
CARD_BG = "rgba(255,255,255,0.03)"
CARD_BR = "rgba(255,255,255,0.08)"

ALL_TEAMS = [
    "ANA","ARI","BOS","BUF","CAR","CGY","CHI","COL","CBJ","DAL",
    "DET","EDM","FLA","LAK","MIN","MTL","NSH","NJD","NYI","NYR",
    "OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WSH","WPG",
]

# ── Helper: comparison HTML table ───────────────────────────────────────────────

def _cmp_table(rows: list[dict], name1: str, name2: str) -> str:
    """Render a side-by-side HTML comparison table.

    rows = [{"label": str, "v1": val, "v2": val, "higher_better": bool}]
    """
    header = (
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
        f"<thead><tr>"
        f"<th style='text-align:left;padding:8px 12px;color:{MUTED};font-size:10px;"
        f"text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid {CARD_BR};'>Metric</th>"
        f"<th style='text-align:center;padding:8px 12px;color:#fff;font-weight:700;"
        f"border-bottom:1px solid {CARD_BR};'>{name1}</th>"
        f"<th style='text-align:center;padding:8px 12px;color:{MUTED};font-size:10px;"
        f"border-bottom:1px solid {CARD_BR};'>VS</th>"
        f"<th style='text-align:center;padding:8px 12px;color:#fff;font-weight:700;"
        f"border-bottom:1px solid {CARD_BR};'>{name2}</th>"
        f"</tr></thead><tbody>"
    )
    body = ""
    for row in rows:
        label      = row["label"]
        v1         = row["v1"]
        v2         = row["v2"]
        higher_ok  = row.get("higher_better", True)
        neutral    = row.get("neutral", False)

        try:
            f1, f2 = float(v1), float(v2)
            if neutral or f1 == f2:
                c1 = c2 = "#fff"
            elif (f1 > f2) == higher_ok:
                c1, c2 = GREEN, MUTED
            else:
                c1, c2 = MUTED, GREEN
        except (TypeError, ValueError):
            c1 = c2 = "#fff"

        disp1 = "—" if v1 is None else v1
        disp2 = "—" if v2 is None else v2

        body += (
            f"<tr>"
            f"<td style='padding:8px 12px;color:{MUTED};font-size:11px;"
            f"text-transform:uppercase;letter-spacing:0.05em;"
            f"border-bottom:1px solid rgba(255,255,255,0.04);'>{label}</td>"
            f"<td style='padding:8px 12px;text-align:center;font-weight:700;"
            f"color:{c1};border-bottom:1px solid rgba(255,255,255,0.04);'>{disp1}</td>"
            f"<td style='padding:8px 12px;text-align:center;color:{MUTED};font-size:10px;"
            f"border-bottom:1px solid rgba(255,255,255,0.04);'>—</td>"
            f"<td style='padding:8px 12px;text-align:center;font-weight:700;"
            f"color:{c2};border-bottom:1px solid rgba(255,255,255,0.04);'>{disp2}</td>"
            f"</tr>"
        )
    return (
        f"<div style='background:{CARD_BG};border:1px solid {CARD_BR};"
        f"border-radius:6px;overflow:hidden;margin-bottom:20px;'>"
        f"{header}{body}</tbody></table></div>"
    )


# ── Tabs ────────────────────────────────────────────────────────────────────────
tab_players, tab_teams = st.tabs(["Players", "Teams"])


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYER TAB
# ═══════════════════════════════════════════════════════════════════════════════
with tab_players:
    col1, col2 = st.columns(2)

    with col1:
        search1 = st.text_input("Search player 1", placeholder="e.g. Auston Matthews", key="p1_search")
    with col2:
        search2 = st.text_input("Search player 2", placeholder="e.g. Leon Draisaitl", key="p2_search")

    PLAYER_SQL = """
        SELECT CAST(player_id AS VARCHAR) AS player_id,
               player_first_name || ' ' || player_last_name AS name,
               team_abbr, position, gp_season,
               goals_season, assists_season,
               ROUND(pts_avg_5g,  2) AS pts_avg_5g,
               ROUND(pts_avg_20g, 2) AS pts_avg_20g,
               ROUND(pts_zscore_5v20, 2) AS pts_zscore_5v20,
               ROUND(toi_avg_10g / 60.0, 2) AS toi_min_avg
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND LOWER(player_first_name || ' ' || player_last_name) LIKE LOWER('%{search}%')
        ORDER BY gp_season DESC
        LIMIT 10
    """

    p1_df = pd.DataFrame()
    p2_df = pd.DataFrame()
    p1_row = None
    p2_row = None

    # ── Player 1 search ───────────────────────────────────────────────────────
    if search1.strip():
        try:
            p1_df = query_fresh(PLAYER_SQL.format(search=search1.strip().replace("'", "''")))
        except Exception as e:
            inline_error(f"Search error: {e}")

    # ── Player 2 search ───────────────────────────────────────────────────────
    if search2.strip():
        try:
            p2_df = query_fresh(PLAYER_SQL.format(search=search2.strip().replace("'", "''")))
        except Exception as e:
            inline_error(f"Search error: {e}")

    # ── Selectboxes ───────────────────────────────────────────────────────────
    sel_col1, sel_col2 = st.columns(2)

    with sel_col1:
        if not p1_df.empty:
            p1_options = p1_df["name"].tolist()
            p1_choice  = st.selectbox("Select player 1", p1_options, key="p1_select")
            p1_row     = p1_df[p1_df["name"] == p1_choice].iloc[0]
        elif search1.strip():
            st.caption("No players found.")

    with sel_col2:
        if not p2_df.empty:
            p2_options = p2_df["name"].tolist()
            p2_choice  = st.selectbox("Select player 2", p2_options, key="p2_select")
            p2_row     = p2_df[p2_df["name"] == p2_choice].iloc[0]
        elif search2.strip():
            st.caption("No players found.")

    # ── Comparison ────────────────────────────────────────────────────────────
    if p1_row is not None and p2_row is not None:
        p1_name = p1_row["name"]
        p2_name = p2_row["name"]

        st.markdown(
            f"<p style='color:{MUTED};font-size:11px;margin:4px 0 12px;'>"
            f"{p1_row['team_abbr']} · {p1_row['position']}  vs  "
            f"{p2_row['team_abbr']} · {p2_row['position']}</p>",
            unsafe_allow_html=True,
        )

        rows = [
            {"label": "GP (season)",      "v1": p1_row["gp_season"],       "v2": p2_row["gp_season"],       "higher_better": True},
            {"label": "Goals",            "v1": p1_row["goals_season"],     "v2": p2_row["goals_season"],     "higher_better": True},
            {"label": "Assists",          "v1": p1_row["assists_season"],   "v2": p2_row["assists_season"],   "higher_better": True},
            {"label": "Pts / 5g avg",     "v1": p1_row["pts_avg_5g"],       "v2": p2_row["pts_avg_5g"],       "higher_better": True},
            {"label": "Pts / 20g avg",    "v1": p1_row["pts_avg_20g"],      "v2": p2_row["pts_avg_20g"],      "higher_better": True},
            {"label": "Momentum (σ)",     "v1": p1_row["pts_zscore_5v20"], "v2": p2_row["pts_zscore_5v20"], "higher_better": True},
            {"label": "TOI avg (min)",    "v1": p1_row["toi_min_avg"],      "v2": p2_row["toi_min_avg"],      "neutral": True},
        ]

        st.markdown(_cmp_table(rows, p1_name, p2_name), unsafe_allow_html=True)

        # ── Plotly grouped bar chart ──────────────────────────────────────────
        chart_metrics = ["goals_season", "assists_season", "pts_avg_5g", "pts_avg_20g"]
        chart_labels  = ["Goals", "Assists", "Pts/5g", "Pts/20g"]

        chart_data = pd.DataFrame({
            "Metric": chart_labels * 2,
            "Value":  [float(p1_row[m] or 0) for m in chart_metrics] +
                      [float(p2_row[m] or 0) for m in chart_metrics],
            "Player": [p1_name] * len(chart_metrics) + [p2_name] * len(chart_metrics),
        })

        fig = px.bar(
            chart_data, x="Metric", y="Value", color="Player", barmode="group",
            color_discrete_sequence=[GREEN, BLUE],
            template="plotly_dark",
            height=300,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fff",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
        st.plotly_chart(fig, use_container_width=True)

        # ── Ask AI button ─────────────────────────────────────────────────────
        if st.button("Ask AI to compare these players", key="ai_players", type="primary"):
            st.session_state["chat_prefill"] = (
                f"Compare {p1_name} and {p2_name}'s stats this season"
            )
            st.switch_page("pages/5_Chat.py")

    elif search1.strip() or search2.strip():
        empty_state(
            "Search for two players to compare",
            "Enter part of a player's name in each search box above.",
        )
    else:
        empty_state(
            "Search for two players to compare",
            "Enter part of a player's name in each search box above.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM TAB
# ═══════════════════════════════════════════════════════════════════════════════
with tab_teams:
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        team1 = st.selectbox("Team 1", ALL_TEAMS, index=ALL_TEAMS.index("TOR"), key="cmp_team1")
    with t_col2:
        team2 = st.selectbox("Team 2", ALL_TEAMS, index=ALL_TEAMS.index("BOS"), key="cmp_team2")

    STANDINGS_SQL = """
        SELECT wins, losses, otLosses, points, gamesPlayed, goalFor, goalAgainst
        FROM standings
        WHERE season = (SELECT MAX(season) FROM standings)
          AND teamAbbrev = '{abbr}'
        LIMIT 1
    """
    ROLLING_SQL = """
        SELECT pts_zscore_5v20, wins_last_5, gf_avg_10g, ga_avg_10g
        FROM team_rolling_stats
        WHERE team_abbr = '{abbr}'
          AND game_recency_rank = 1
        LIMIT 1
    """

    def _load_team(abbr: str) -> dict | None:
        try:
            st_df  = query_fresh(STANDINGS_SQL.format(abbr=abbr))
            rol_df = query_fresh(ROLLING_SQL.format(abbr=abbr))
            if st_df.empty:
                return None
            row = st_df.iloc[0].to_dict()
            if not rol_df.empty:
                row.update(rol_df.iloc[0].to_dict())
            return row
        except Exception as e:
            inline_error(f"Could not load {abbr}: {e}")
            return None

    t1_data = _load_team(team1)
    t2_data = _load_team(team2)

    def _safe(d: dict | None, key: str, fmt: str = "{}") -> str:
        if d is None or key not in d or d[key] is None:
            return "—"
        try:
            val = d[key]
            return fmt.format(round(float(val), 2) if isinstance(val, float) else val)
        except Exception:
            return str(d.get(key, "—"))

    if t1_data and t2_data:
        # Goal diff
        def _gdiff(d: dict | None) -> str:
            if d is None:
                return "—"
            try:
                return str(int(float(d["goalFor"])) - int(float(d["goalAgainst"])))
            except Exception:
                return "—"

        def _wl(d: dict | None) -> str:
            if d is None:
                return "—"
            try:
                return f"{int(float(d['wins']))}-{int(float(d['losses']))}-{int(float(d['otLosses']))}"
            except Exception:
                return "—"

        rows = [
            {"label": "Points",        "v1": _safe(t1_data, "points"),         "v2": _safe(t2_data, "points"),         "higher_better": True},
            {"label": "W-L-OTL",       "v1": _wl(t1_data),                     "v2": _wl(t2_data),                     "neutral": True},
            {"label": "GP",            "v1": _safe(t1_data, "gamesPlayed"),     "v2": _safe(t2_data, "gamesPlayed"),     "neutral": True},
            {"label": "Goal diff",     "v1": _gdiff(t1_data),                  "v2": _gdiff(t2_data),                  "higher_better": True},
            {"label": "Goals for",     "v1": _safe(t1_data, "goalFor"),         "v2": _safe(t2_data, "goalFor"),         "higher_better": True},
            {"label": "Goals against", "v1": _safe(t1_data, "goalAgainst"),     "v2": _safe(t2_data, "goalAgainst"),     "higher_better": False},
            {"label": "Momentum (σ)",  "v1": _safe(t1_data, "pts_zscore_5v20"),"v2": _safe(t2_data, "pts_zscore_5v20"),"higher_better": True},
            {"label": "Wins last 5",   "v1": _safe(t1_data, "wins_last_5"),    "v2": _safe(t2_data, "wins_last_5"),    "higher_better": True},
            {"label": "GF avg 10g",    "v1": _safe(t1_data, "gf_avg_10g"),     "v2": _safe(t2_data, "gf_avg_10g"),     "higher_better": True},
            {"label": "GA avg 10g",    "v1": _safe(t1_data, "ga_avg_10g"),     "v2": _safe(t2_data, "ga_avg_10g"),     "higher_better": False},
        ]

        st.markdown(_cmp_table(rows, team1, team2), unsafe_allow_html=True)

        # ── Chart ─────────────────────────────────────────────────────────────
        def _fval(d: dict | None, key: str) -> float:
            try:
                return float(d[key]) if d and d.get(key) is not None else 0.0
            except Exception:
                return 0.0

        t_chart_metrics = ["points", "goalFor", "goalAgainst", "gf_avg_10g", "ga_avg_10g"]
        t_chart_labels  = ["Points", "Goals For", "Goals Against", "GF avg 10g", "GA avg 10g"]

        t_chart_data = pd.DataFrame({
            "Metric": t_chart_labels * 2,
            "Value":  [_fval(t1_data, m) for m in t_chart_metrics] +
                      [_fval(t2_data, m) for m in t_chart_metrics],
            "Team":   [team1] * len(t_chart_metrics) + [team2] * len(t_chart_metrics),
        })

        fig2 = px.bar(
            t_chart_data, x="Metric", y="Value", color="Team", barmode="group",
            color_discrete_sequence=[GREEN, BLUE],
            template="plotly_dark",
            height=300,
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fff",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig2.update_xaxes(showgrid=False)
        fig2.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
        st.plotly_chart(fig2, use_container_width=True)

        # ── Ask AI button ─────────────────────────────────────────────────────
        if st.button("Ask AI to compare these teams", key="ai_teams", type="primary"):
            st.session_state["chat_prefill"] = (
                f"Compare {team1} and {team2}'s performance and stats this season"
            )
            st.switch_page("pages/5_Chat.py")

    else:
        inline_error("Could not load data for one or both teams. Please try again.")

data_source_footer()
