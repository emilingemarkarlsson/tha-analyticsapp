"""Teams page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import data_source_footer, methodology_note

st.set_page_config(page_title="Teams – THA Analytics", page_icon="https://assets.nhle.com/logos/nhl/svg/NHL_light.svg", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

# Handle inbound navigation from Standings / Players via query params
_team_param = st.query_params.get("team")
if _team_param:
    st.session_state["teams_selected"] = _team_param
    st.query_params.clear()

ALL_TEAMS = [
    "ANA","ARI","BOS","BUF","CAR","CGY","CHI","COL","CBJ","DAL",
    "DET","EDM","FLA","LAK","MIN","MTL","NSH","NJD","NYI","NYR",
    "OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WSH","WPG",
]
TEAM_NAMES = {
    "ANA":"Anaheim Ducks","ARI":"Arizona Coyotes","BOS":"Boston Bruins",
    "BUF":"Buffalo Sabres","CAR":"Carolina Hurricanes","CGY":"Calgary Flames",
    "CHI":"Chicago Blackhawks","COL":"Colorado Avalanche","CBJ":"Columbus Blue Jackets",
    "DAL":"Dallas Stars","DET":"Detroit Red Wings","EDM":"Edmonton Oilers",
    "FLA":"Florida Panthers","LAK":"Los Angeles Kings","MIN":"Minnesota Wild",
    "MTL":"Montreal Canadiens","NSH":"Nashville Predators","NJD":"New Jersey Devils",
    "NYI":"New York Islanders","NYR":"New York Rangers","OTT":"Ottawa Senators",
    "PHI":"Philadelphia Flyers","PIT":"Pittsburgh Penguins","SEA":"Seattle Kraken",
    "SJS":"San Jose Sharks","STL":"St. Louis Blues","TBL":"Tampa Bay Lightning",
    "TOR":"Toronto Maple Leafs","UTA":"Utah Hockey Club","VAN":"Vancouver Canucks",
    "VGK":"Vegas Golden Knights","WSH":"Washington Capitals","WPG":"Winnipeg Jets",
}
POPULAR_TEAMS = ["TOR","EDM","BOS","NYR","MTL","TBL","COL","VGK"]

# Quick-pick chips for popular teams
st.markdown(
    "<p style='color:rgba(255,255,255,0.3);font-size:9px;font-weight:700;text-transform:uppercase;"
    "letter-spacing:0.1em;margin:0 0 4px;'>Quick pick</p>",
    unsafe_allow_html=True,
)
qcols = st.columns(len(POPULAR_TEAMS))
for i, t in enumerate(POPULAR_TEAMS):
    with qcols[i]:
        if st.button(t, key=f"qpick_{t}", use_container_width=True):
            st.session_state["teams_selected"] = t
            st.rerun()

if "teams_selected" in st.session_state and st.session_state["teams_selected"] in ALL_TEAMS:
    default_idx = ALL_TEAMS.index(st.session_state["teams_selected"])
else:
    default_idx = ALL_TEAMS.index("TOR")

team = st.selectbox("Select team", ALL_TEAMS, index=default_idx, label_visibility="collapsed",
                    key="teams_selectbox")
st.session_state["teams_selected"] = team

from lib.components import page_header
page_header(TEAM_NAMES.get(team, team), "Current season · Regular season", data_date=get_data_date())

try:
    df_season = query_fresh(f"""
        SELECT pts_cumulative, gp_season, wins_last_5, losses_last_5,
               gf_avg_10g, ga_avg_10g, pts_zscore_5v20
        FROM team_rolling_stats
        WHERE team_abbr = '{team}' AND game_recency_rank = 1
        LIMIT 1
    """)
    df_team_stats = query_fresh(f"""
        SELECT ts.powerPlayPct, ts.penaltyKillPct,
               ts.shotsForPerGame, ts.shotsAgainstPerGame, ts.faceoffWinPct
        FROM team_stats ts
        JOIN standings st ON st.teamName = ts.teamFullName AND st.season = ts.season
        WHERE st.teamAbbrev = '{team}'
          AND ts.season = (SELECT MAX(season) FROM team_stats)
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

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
    with c1:
        st.metric("Points", int(row["pts_cumulative"]), f"{int(row['gp_season'])} GP")
    with c2:
        st.metric("Last 5 Record", f"{int(row['wins_last_5'])}–{int(row['losses_last_5'])}", "W – L")
    with c3:
        st.metric("GF / 10", f"{float(row['gf_avg_10g']):.2f}", f"GA: {float(row['ga_avg_10g']):.2f}")
    with c4:
        st.metric("Momentum", fz_str, "5g vs 20g baseline")
    with c5:
        if st.button("Ask AI", key="ask_ai_team", type="secondary", use_container_width=True):
            st.session_state["chat_prefill"] = (
                f"How has {TEAM_NAMES.get(team, team)} been performing this season? "
                f"Include their recent form, goals for/against, and any notable trends."
            )
            st.switch_page("pages/5_Chat.py")

# ── Special teams row ─────────────────────────────────────────────────────────
if not df_team_stats.empty:
    ts = df_team_stats.iloc[0]
    pp_pct = float(ts["powerPlayPct"]) * 100
    pk_pct = float(ts["penaltyKillPct"]) * 100
    sf_g   = float(ts["shotsForPerGame"])
    sa_g   = float(ts["shotsAgainstPerGame"])
    fo_pct = float(ts["faceoffWinPct"]) * 100

    pp_color = "#f97316" if pp_pct >= 25 else ("#5a8f4e" if pp_pct >= 20 else "#8896a8")
    pk_color = "#f97316" if pk_pct >= 83 else ("#5a8f4e" if pk_pct >= 78 else "#8896a8")
    sf_color = "#5a8f4e" if sf_g >= 32 else ("#8896a8" if sf_g >= 28 else "#87ceeb")

    st.markdown(
        f"""<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:4px;">
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                      border-radius:5px;padding:8px 16px;min-width:80px;">
            <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">PP%</div>
            <div style="color:{pp_color};font-weight:800;font-size:18px;">{pp_pct:.1f}<span style="font-size:11px;font-weight:400;">%</span></div>
          </div>
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                      border-radius:5px;padding:8px 16px;min-width:80px;">
            <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">PK%</div>
            <div style="color:{pk_color};font-weight:800;font-size:18px;">{pk_pct:.1f}<span style="font-size:11px;font-weight:400;">%</span></div>
          </div>
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                      border-radius:5px;padding:8px 16px;min-width:80px;">
            <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">SF/g</div>
            <div style="color:{sf_color};font-weight:800;font-size:18px;">{sf_g:.1f}</div>
          </div>
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                      border-radius:5px;padding:8px 16px;min-width:80px;">
            <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">SA/g</div>
            <div style="color:#8896a8;font-weight:800;font-size:18px;">{sa_g:.1f}</div>
          </div>
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                      border-radius:5px;padding:8px 16px;min-width:80px;">
            <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">FO%</div>
            <div style="color:#8896a8;font-weight:800;font-size:18px;">{fo_pct:.1f}<span style="font-size:11px;font-weight:400;">%</span></div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

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

# ── Team Comparison ───────────────────────────────────────────────────────────
st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='font-size:10px;font-weight:700;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Compare with other teams · cumulative points this season</p>",
    unsafe_allow_html=True,
)
compare_options = [t for t in ALL_TEAMS if t != team]
compare_sel = st.multiselect(
    "", compare_options, max_selections=3,
    placeholder="Add up to 3 teams to compare...",
    label_visibility="collapsed", key="cmp_teams",
)
all_cmp = [team] + (compare_sel or [])
cmp_in = "','".join(all_cmp)
try:
    df_cmp = query_fresh(f"""
        SELECT
            team_abbr,
            game_date,
            SUM(TRY_CAST(team_points AS DOUBLE)) OVER (
                PARTITION BY team_abbr ORDER BY game_date
                ROWS UNBOUNDED PRECEDING
            ) AS cum_pts,
            ROW_NUMBER() OVER (PARTITION BY team_abbr ORDER BY game_date) AS game_num
        FROM team_game_stats
        WHERE team_abbr IN ('{cmp_in}')
          AND game_type = '2'
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
        ORDER BY team_abbr, game_date
    """)
except Exception:
    df_cmp = pd.DataFrame()

if not df_cmp.empty:
    CMP_COLORS = ["#5a8f4e", "#f97316", "#87ceeb", "#c41e3a"]
    fig_cmp = go.Figure()
    for i, t in enumerate(all_cmp):
        t_df = df_cmp[df_cmp["team_abbr"] == t].sort_values("game_num")
        if t_df.empty:
            continue
        color = CMP_COLORS[i % len(CMP_COLORS)]
        last = t_df.iloc[-1]
        fig_cmp.add_trace(go.Scatter(
            x=t_df["game_num"],
            y=t_df["cum_pts"],
            mode="lines",
            name=t,
            line=dict(color=color, width=2.5 if i == 0 else 1.8),
            opacity=1.0 if i == 0 else 0.85,
        ))
        fig_cmp.add_annotation(
            x=float(last["game_num"]) + 0.5,
            y=float(last["cum_pts"]),
            text=f"<b>{t}</b>  {int(last['cum_pts'])}",
            showarrow=False, xanchor="left",
            font=dict(size=9, color=color),
        )
    fig_cmp.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8896a8", font_size=11,
        margin=dict(l=0, r=90, t=10, b=30),
        height=220,
        showlegend=False,
        xaxis=dict(title="Game #", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
        yaxis=dict(title="Cumulative Points", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

data_source_footer('Form (σ) = last 5 games vs 20-game baseline · pts_zscore_5v20')
