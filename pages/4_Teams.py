"""Teams page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.components import data_source_footer, methodology_note

st.set_page_config(page_title="Teams – THA Analytics", layout="wide")
_render_sidebar()

ALL_TEAMS = [
    "ANA","ARI","BOS","BUF","CAR","CGY","CHI","COL","CBJ","DAL",
    "DET","EDM","FLA","LAK","MIN","MTL","NSH","NJD","NYI","NYR",
    "OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WSH","WPG",
]

team = st.selectbox("Select team", ALL_TEAMS, index=ALL_TEAMS.index("TOR"), label_visibility="collapsed")

from lib.components import page_header
page_header(team, "Current season · Regular season", data_date=get_data_date())

try:
    df_season = query_fresh(f"""
        SELECT pts_cumulative, gp_season, wins_last_5, losses_last_5,
               gf_avg_10g, ga_avg_10g, pts_zscore_5v20
        FROM team_rolling_stats
        WHERE team_abbr = '{team}' AND game_recency_rank = 1
        LIMIT 1
    """)
    df_games = query_fresh(f"""
        SELECT game_date, opponent_abbr, is_home, goals_for, goals_against, team_points
        FROM team_game_stats
        WHERE team_abbr = '{team}'
          AND game_type = '2'
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
        ORDER BY game_date DESC
        LIMIT 15
    """)
    df_insights = query_fresh(f"""
        SELECT insight_type, entity_name, headline, zscore, game_date
        FROM agent_insights
        WHERE team_abbr = '{team}'
        ORDER BY generated_at DESC
        LIMIT 5
    """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ── Stat cards ────────────────────────────────────────────────────────────────
if not df_season.empty:
    row = df_season.iloc[0]
    fz = float(row["pts_zscore_5v20"])
    fz_color = "#f97316" if fz >= 0 else "#87ceeb"
    fz_str = f"+{fz:.2f}σ" if fz >= 0 else f"{fz:.2f}σ"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Points", int(row["pts_cumulative"]), f"{int(row['gp_season'])} GP")
    with c2:
        st.metric("Last 5 Record", f"{int(row['wins_last_5'])}–{int(row['losses_last_5'])}", "W – L")
    with c3:
        st.metric("GF / 10", f"{float(row['gf_avg_10g']):.2f}", f"GA: {float(row['ga_avg_10g']):.2f}")
    with c4:
        st.metric("Form", fz_str, "5 vs 20 game")

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ── Recent games + Goal trend ─────────────────────────────────────────────────
col_games, col_insights = st.columns([2, 1], gap="large")

with col_games:
    st.markdown(
        "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:10px;'>Recent Games</p>",
        unsafe_allow_html=True,
    )

    # Plotly bar chart for goals
    if not df_games.empty:
        df_chart = df_games.sort_values("game_date").tail(10)
        fig = go.Figure()
        fig.add_bar(
            x=df_chart["game_date"].astype(str).str[:10],
            y=df_chart["goals_for"],
            name="GF",
            marker_color="#5a8f4e",
            opacity=0.9,
        )
        fig.add_bar(
            x=df_chart["game_date"].astype(str).str[:10],
            y=df_chart["goals_against"],
            name="GA",
            marker_color="#c41e3a",
            opacity=0.7,
        )
        fig.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8896a8",
            font_size=11,
            margin=dict(l=0, r=0, t=10, b=30),
            height=160,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if df_games.empty:
        st.info("No games found.")
    else:
        rows_html = ""
        for _, g in df_games.iterrows():
            pts = int(g["team_points"] or 0)
            win, otl = pts == 2, pts == 1
            goals_for = g["goals_for"]
            goals_against = g["goals_against"]
            score_str = f"{int(goals_for)}–{int(goals_against)}" if goals_for is not None and goals_against is not None else "–"
            res = "W" if win else ("OTL" if otl else "L")
            res_color = "#5a8f4e" if win else ("#87ceeb" if otl else "#c41e3a")
            res_bg = "rgba(90,143,78,0.15)" if win else ("rgba(135,206,235,0.1)" if otl else "rgba(196,30,58,0.15)")
            ha = "HOME" if g["is_home"] else "AWAY"
            rows_html += f"""
            <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
              <td style="padding:8px 14px;color:#8896a8;font-size:12px;">{str(g['game_date'])[:10]}</td>
              <td style="padding:8px 8px;color:#fff;font-weight:600;font-size:13px;">{g['opponent_abbr']}</td>
              <td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:11px;">{ha}</td>
              <td style="text-align:center;padding:8px 8px;color:#fff;font-family:monospace;font-size:13px;">{score_str}</td>
              <td style="text-align:center;padding:8px 14px;">
                <span style="color:{res_color};background:{res_bg};padding:2px 7px;border-radius:3px;font-size:11px;font-weight:700;">{res}</span>
              </td>
            </tr>"""

        st.markdown(
            f"""<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">
                  <th style="text-align:left;padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Date</th>
                  <th style="text-align:left;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">Opp</th>
                  <th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">H/A</th>
                  <th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">Score</th>
                  <th style="text-align:center;padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;">Result</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table></div>""",
            unsafe_allow_html=True,
        )

with col_insights:
    st.markdown(
        "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:10px;'>AI Insights</p>",
        unsafe_allow_html=True,
    )
    if df_insights.empty:
        st.markdown(
            f"<p style='color:#8896a8;font-size:12px;'>No recent insights for {team}.</p>",
            unsafe_allow_html=True,
        )
    else:
        for _, ins in df_insights.iterrows():
            z = float(ins["zscore"])
            z_color = "#f97316" if z >= 0 else "#87ceeb"
            z_str = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"
            headline = str(ins["headline"]) if ins["headline"] else ""
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                              border-radius:5px;padding:10px 12px;margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span style="color:#fff;font-size:12px;font-weight:600;">{ins['entity_name']}</span>
                    <span style="color:{z_color};font-family:monospace;font-size:12px;font-weight:700;">{z_str}</span>
                  </div>
                  {"<p style='color:#8896a8;font-size:11px;line-height:1.5;margin:0;'>" + headline + "</p>" if headline else ""}
                </div>""",
                unsafe_allow_html=True,
            )

data_source_footer('Form (σ) = last 5 games vs 20-game baseline · pts_zscore_5v20')
