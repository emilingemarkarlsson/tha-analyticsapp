"""Team History – franchise trends, season arc and playoff history."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from lib.db import query, query_fresh, team_career, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.components import (
    page_header, section_label, data_source_footer,
    stat_card_row, tier_badge_html, methodology_note,
)

st.set_page_config(page_title="Team History – THA Analytics", layout="wide")
_render_sidebar()

ALL_TEAMS = [
    "ANA","ARI","BOS","BUF","CAR","CGY","CHI","COL","CBJ","DAL",
    "DET","EDM","FLA","LAK","MIN","MTL","NSH","NJD","NYI","NYR",
    "OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WSH","WPG",
]

# ── Load top trending teams (cached) ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _top_trending_teams() -> pd.DataFrame:
    return query("""
        SELECT team_abbr,
               ROUND(pts_zscore_5v20, 2) AS z,
               wins_last_5,
               ROUND(gf_avg_10g, 1) AS gf10,
               ROUND(ga_avg_10g, 1) AS ga10
        FROM team_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
        ORDER BY pts_zscore_5v20 DESC
        LIMIT 8
    """)

df_top = _top_trending_teams()

page_header("Team History", "Franchise arc · season-by-season · playoff history", data_date=get_data_date())

# ── Top trending teams quick-select ────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Trending teams right now</p>",
    unsafe_allow_html=True,
)

# Auto-set default BEFORE any widgets
if not st.session_state.get("th_selected") and not df_top.empty:
    st.session_state["th_selected"] = df_top.iloc[0]["team_abbr"]

if not df_top.empty:
    cols = st.columns(min(len(df_top), 8))
    for i, (_, r) in enumerate(df_top.iterrows()):
        with cols[i % 8]:
            is_active = st.session_state.get("th_selected") == r["team_abbr"]
            if st.button(
                r["team_abbr"],
                key=f"top_{r['team_abbr']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                help=f"W5: {int(r['wins_last_5'])}  ·  GF/10: {r['gf10']}  ·  Form: {r['z']:+.2f}σ",
            ):
                st.session_state["th_selected"] = r["team_abbr"]
                st.rerun()

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

# ── Team selector ──────────────────────────────────────────────────────────────
default_idx = ALL_TEAMS.index(st.session_state.get("th_selected", "TOR"))
team = st.selectbox(
    "",
    ALL_TEAMS,
    index=default_idx,
    label_visibility="collapsed",
    key="th_selectbox",
)
# Keep session state in sync when user picks from dropdown
if team != st.session_state.get("th_selected"):
    st.session_state["th_selected"] = team

# ── Load franchise data ────────────────────────────────────────────────────────
try:
    df = team_career(team)
    df_form = query_fresh(f"""
        SELECT game_date, goals_for, goals_against, team_points, opponent_abbr, is_home
        FROM team_game_stats
        WHERE team_abbr = '{team}'
          AND game_type = '2'
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
        ORDER BY game_date
    """)
    df_playoffs = query_fresh(f"""
        SELECT season, playoff_round, series_title,
               top_seed_team_abbr, bottom_seed_team_abbr,
               winning_team_id, top_seed_team_id, bottom_seed_team_id
        FROM playoff_brackets
        WHERE top_seed_team_abbr = '{team}' OR bottom_seed_team_abbr = '{team}'
        ORDER BY season, playoff_round
    """)
    df_current = query_fresh(f"""
        SELECT pts_cumulative, gp_season, wins_last_5, losses_last_5,
               gf_avg_10g, ga_avg_10g, pts_zscore_5v20
        FROM team_rolling_stats
        WHERE team_abbr = '{team}' AND game_recency_rank = 1
        LIMIT 1
    """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

if df.empty:
    st.warning(f"No historical data found for {team}.")
    st.stop()

# ── Derive season labels ───────────────────────────────────────────────────────
def season_label(s: int) -> str:
    s = str(s)
    return f"{s[:4]}-{s[6:]}"

df["season_label"] = df["season"].apply(season_label)
df["pts_per_82"] = (df["points"] / df["gamesPlayed"] * 82).round(1)

# ── Franchise summary values ───────────────────────────────────────────────────
total_seasons = len(df)
best_row = df.loc[df["points"].idxmax()]
best_season = season_label(int(best_row["season"]))
best_pts = int(best_row["points"])

playoff_seasons = df_playoffs["season"].nunique() if not df_playoffs.empty else 0
max_round = int(df_playoffs["playoff_round"].max()) if not df_playoffs.empty else 0
cup_wins = 0
if not df_playoffs.empty:
    finals = df_playoffs[df_playoffs["playoff_round"] == 4]
    for _, row in finals.iterrows():
        abbr = team
        won_as_top = (row["top_seed_team_abbr"] == abbr and
                      row["winning_team_id"] == row["top_seed_team_id"])
        won_as_bot = (row["bottom_seed_team_abbr"] == abbr and
                      row["winning_team_id"] == row["bottom_seed_team_id"])
        if won_as_top or won_as_bot:
            cup_wins += 1

current_pts = int(df_current.iloc[0]["pts_cumulative"]) if not df_current.empty else "—"
cur_z = float(df_current.iloc[0]["pts_zscore_5v20"]) if not df_current.empty else 0.0

round_labels = {0: "Qualifiers", 1: "Round 1", 2: "Round 2", 3: "Conf. Final", 4: "Cup Final"}
deepest = round_labels.get(max_round, "—") if max_round > 0 else "—"

# ── Stat cards ─────────────────────────────────────────────────────────────────
stat_card_row([
    {"label": "Seasons analyzed", "value": str(total_seasons), "sub": "2009-10 – present"},
    {"label": "Best season", "value": str(best_pts) + " pts", "sub": best_season, "color": "#f97316"},
    {"label": "Playoff appearances", "value": str(playoff_seasons), "sub": f"Deepest: {deepest}"},
    {"label": "Stanley Cup wins", "value": str(cup_wins) if cup_wins else "0", "sub": "since 2009-10"},
    {"label": "Current season", "value": str(current_pts) + " pts", "sub": tier_badge_html(cur_z, show_z=True)},
])

# ── Franchise narrative ────────────────────────────────────────────────────────
recent = df.tail(3)
recent_trend = "improving" if recent["points"].is_monotonic_increasing else (
    "declining" if recent["points"].is_monotonic_decreasing else "fluctuating"
)
avg_pts = df["points"].mean()
above_avg = df[df["points"] >= 96]  # ~playoff threshold
worst_row = df.loc[df["points"].idxmin()]

narrative = (
    f"**{team}** has {total_seasons} seasons of data since 2009-10, averaging "
    f"**{avg_pts:.0f} points** per season. "
    f"Their best campaign was **{best_season}** ({best_pts} pts). "
)
if playoff_seasons > 0:
    narrative += f"The franchise has made the playoffs **{playoff_seasons}** times, reaching the {deepest.lower()}. "
if len(above_avg) > 0:
    narrative += f"They have finished with 96+ points in **{len(above_avg)}** seasons. "
narrative += f"Over the last 3 seasons, performance has been **{recent_trend}**."

st.markdown(
    f"<div style='background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);"
    f"border-radius:5px;padding:14px 18px;margin-bottom:20px;color:#c8d4e0;font-size:13px;line-height:1.7;'>"
    f"{narrative}</div>",
    unsafe_allow_html=True,
)

# ── Chart helpers ──────────────────────────────────────────────────────────────
LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#8896a8",
    font_size=11,
    margin=dict(l=0, r=10, t=30, b=30),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(size=10), bgcolor="rgba(0,0,0,0)",
    ),
)

seasons = df["season_label"].tolist()
current_season = seasons[-1]
is_current_in_progress = df.iloc[-1]["gamesPlayed"] < 80

# ── 1. Points Arc ──────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:24px 0 6px;'>"
    "Franchise Points Arc · season totals</p>",
    unsafe_allow_html=True,
)

fig_arc = go.Figure()

# Playoff threshold band
fig_arc.add_hrect(y0=96, y1=120, fillcolor="rgba(90,143,78,0.05)",
                  line_width=0, annotation_text="playoff zone", annotation_position="top right",
                  annotation_font=dict(size=9, color="#5a8f4e"))

# PTS line
pts_colors = ["rgba(90,143,78,0.6)" if not is_current_in_progress or i < len(df)-1
              else "rgba(90,143,78,0.35)" for i in range(len(df))]
fig_arc.add_trace(go.Scatter(
    x=seasons, y=df["points"],
    mode="lines+markers",
    name="Points",
    line=dict(color="#5a8f4e", width=2.5),
    marker=dict(size=5, color=pts_colors),
    fill="tozeroy",
    fillcolor="rgba(90,143,78,0.07)",
))

# PTS/82 pace line (dashed)
fig_arc.add_trace(go.Scatter(
    x=seasons, y=df["pts_per_82"],
    mode="lines",
    name="Pts/82 pace",
    line=dict(color="#f97316", width=1.5, dash="dot"),
    opacity=0.7,
))

# Playoff threshold line
fig_arc.add_hline(y=96, line_color="rgba(90,143,78,0.3)", line_dash="dash",
                  line_width=1, annotation_text="96 pts", annotation_position="right",
                  annotation_font=dict(size=9, color="#5a8f4e"))

# Annotate best season
best_idx = df["points"].idxmax()
best_s = df.loc[best_idx, "season_label"]
best_p = int(df.loc[best_idx, "points"])
fig_arc.add_annotation(
    x=best_s, y=best_p,
    text=f"Best<br>{best_p} pts",
    showarrow=True, arrowhead=2, arrowcolor="#f97316",
    ax=0, ay=-36, font=dict(size=9, color="#f97316"),
    bgcolor="rgba(0,0,0,0.6)", bordercolor="#f97316",
)

# Current season marker if in progress
if is_current_in_progress:
    cur_pts_val = float(df.iloc[-1]["points"])
    fig_arc.add_annotation(
        x=current_season, y=cur_pts_val,
        text=f"In progress<br>{int(cur_pts_val)} pts",
        showarrow=True, arrowhead=2, arrowcolor="#87ceeb",
        ax=20, ay=-30, font=dict(size=9, color="#87ceeb"),
        bgcolor="rgba(0,0,0,0.6)", bordercolor="rgba(135,206,235,0.4)",
    )

fig_arc.update_layout(height=300, **LAYOUT_BASE)
st.plotly_chart(fig_arc, use_container_width=True, config={"displayModeBar": False})

# ── 2. Goals For / Against Arc ─────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:24px 0 6px;'>"
    "Goals For · Goals Against · Differential</p>",
    unsafe_allow_html=True,
)

fig_goals = go.Figure()

fig_goals.add_trace(go.Scatter(
    x=seasons, y=df["goalFor"],
    mode="lines+markers",
    name="Goals For",
    line=dict(color="#5a8f4e", width=2.5),
    marker=dict(size=4),
    fill="tozeroy",
    fillcolor="rgba(90,143,78,0.08)",
))
fig_goals.add_trace(go.Scatter(
    x=seasons, y=df["goalAgainst"],
    mode="lines+markers",
    name="Goals Against",
    line=dict(color="#c41e3a", width=2),
    marker=dict(size=4),
    fill="tozeroy",
    fillcolor="rgba(196,30,58,0.06)",
))

# Annotate best goal diff season
best_gd_idx = df["goalDifferential"].idxmax()
best_gd_s = df.loc[best_gd_idx, "season_label"]
best_gd_v = int(df.loc[best_gd_idx, "goalDifferential"])
best_gf_v = int(df.loc[best_gd_idx, "goalFor"])
fig_goals.add_annotation(
    x=best_gd_s, y=best_gf_v,
    text=f"+{best_gd_v} GD",
    showarrow=True, arrowhead=2, arrowcolor="#5a8f4e",
    ax=0, ay=-30, font=dict(size=9, color="#5a8f4e"),
    bgcolor="rgba(0,0,0,0.6)", bordercolor="rgba(90,143,78,0.4)",
)

# Annotate worst goal diff season
worst_gd_idx = df["goalDifferential"].idxmin()
worst_gd_s = df.loc[worst_gd_idx, "season_label"]
worst_gd_v = int(df.loc[worst_gd_idx, "goalDifferential"])
worst_ga_v = int(df.loc[worst_gd_idx, "goalAgainst"])
fig_goals.add_annotation(
    x=worst_gd_s, y=worst_ga_v,
    text=f"{worst_gd_v} GD",
    showarrow=True, arrowhead=2, arrowcolor="#c41e3a",
    ax=0, ay=30, font=dict(size=9, color="#c41e3a"),
    bgcolor="rgba(0,0,0,0.6)", bordercolor="rgba(196,30,58,0.4)",
)

fig_goals.update_layout(height=280, **LAYOUT_BASE)
st.plotly_chart(fig_goals, use_container_width=True, config={"displayModeBar": False})

# ── 3. Win % trend ─────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:24px 0 6px;'>"
    "Point % · win consistency</p>",
    unsafe_allow_html=True,
)

fig_pct = go.Figure()
fig_pct.add_hrect(y0=0.55, y1=0.75, fillcolor="rgba(90,143,78,0.05)", line_width=0)
fig_pct.add_hline(y=0.55, line_color="rgba(90,143,78,0.3)", line_dash="dash",
                  line_width=1, annotation_text="55%", annotation_position="right",
                  annotation_font=dict(size=9, color="#5a8f4e"))
fig_pct.add_hline(y=0.50, line_color="rgba(255,255,255,0.15)", line_dash="dot", line_width=1)

fig_pct.add_trace(go.Scatter(
    x=seasons, y=df["pointPctg"],
    mode="lines+markers",
    name="Pt%",
    line=dict(color="#87ceeb", width=2.5),
    marker=dict(size=5),
    fill="tozeroy",
    fillcolor="rgba(135,206,235,0.06)",
))
fig_pct.add_trace(go.Scatter(
    x=seasons, y=df["winPctg"],
    mode="lines",
    name="Win%",
    line=dict(color="#8896a8", width=1.5, dash="dot"),
    opacity=0.7,
))

best_pct_idx = df["pointPctg"].idxmax()
best_pct_s = df.loc[best_pct_idx, "season_label"]
best_pct_v = float(df.loc[best_pct_idx, "pointPctg"])
fig_pct.add_annotation(
    x=best_pct_s, y=best_pct_v,
    text=f"Peak {best_pct_v:.1%}",
    showarrow=True, arrowhead=2, arrowcolor="#87ceeb",
    ax=0, ay=-30, font=dict(size=9, color="#87ceeb"),
    bgcolor="rgba(0,0,0,0.6)", bordercolor="rgba(135,206,235,0.4)",
)

fig_pct.update_layout(
    height=240,
    yaxis=dict(tickformat=".0%", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    **{k: v for k, v in LAYOUT_BASE.items() if k != "yaxis"},
)
st.plotly_chart(fig_pct, use_container_width=True, config={"displayModeBar": False})

# ── 4. Current season form (GF/GA per game) ────────────────────────────────────
if not df_form.empty:
    st.markdown(
        "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin:24px 0 6px;'>"
        "Current season · game-by-game results</p>",
        unsafe_allow_html=True,
    )

    df_form_sorted = df_form.sort_values("game_date")
    dates = df_form_sorted["game_date"].astype(str).str[:10].tolist()
    gf = df_form_sorted["goals_for"].tolist()
    ga = df_form_sorted["goals_against"].tolist()
    pts_vals = df_form_sorted["team_points"].tolist()

    bar_colors_gf = ["#5a8f4e" if p == 2 else ("#87ceeb" if p == 1 else "rgba(90,143,78,0.3)")
                     for p in pts_vals]
    bar_colors_ga = ["rgba(196,30,58,0.5)" if p != 2 else "rgba(196,30,58,0.25)"
                     for p in pts_vals]

    fig_form = go.Figure()
    fig_form.add_bar(x=dates, y=gf, name="GF", marker_color=bar_colors_gf, opacity=0.9)
    fig_form.add_bar(x=dates, y=ga, name="GA", marker_color=bar_colors_ga, opacity=0.7)

    # Rolling 5-game GF average
    gf_series = pd.Series(gf)
    ga_series = pd.Series(ga)
    fig_form.add_trace(go.Scatter(
        x=dates, y=gf_series.rolling(5, min_periods=3).mean().tolist(),
        mode="lines", name="GF 5g avg",
        line=dict(color="#5a8f4e", width=1.5, dash="dot"), opacity=0.8,
    ))
    fig_form.add_trace(go.Scatter(
        x=dates, y=ga_series.rolling(5, min_periods=3).mean().tolist(),
        mode="lines", name="GA 5g avg",
        line=dict(color="#c41e3a", width=1.5, dash="dot"), opacity=0.6,
    ))

    fig_form.update_layout(
        barmode="group", height=200, **LAYOUT_BASE,
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9),
            tickangle=-45, nticks=20,
        ),
    )
    st.plotly_chart(fig_form, use_container_width=True, config={"displayModeBar": False})
    methodology_note("Green bars = win · Blue = OT loss · Faded = regulation loss. Dotted lines = 5-game rolling average.")

# ── 5. Season Table ────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:28px 0 8px;'>Season by Season</p>",
    unsafe_allow_html=True,
)

rows_html = ""
for _, r in df.sort_values("season", ascending=False).iterrows():
    gd = int(r["goalDifferential"])
    gd_color = "#5a8f4e" if gd > 0 else ("#c41e3a" if gd < 0 else "#8896a8")
    gd_str = f"+{gd}" if gd > 0 else str(gd)
    pts_v = int(r["points"])
    pts_color = "#f97316" if pts_v == best_pts else ("#5a8f4e" if pts_v >= 96 else "#fff")
    ptpct = float(r["pointPctg"])
    ptpct_color = "#5a8f4e" if ptpct >= 0.55 else ("#c41e3a" if ptpct < 0.45 else "#8896a8")

    # Playoff appearance for this season
    if not df_playoffs.empty:
        seas_playoffs = df_playoffs[df_playoffs["season"] == r["season"]]
        max_r = seas_playoffs["playoff_round"].max() if not seas_playoffs.empty else 0
        pl_badge = (
            f"<span style='background:rgba(249,115,22,0.15);border:1px solid rgba(249,115,22,0.4);"
            f"color:#f97316;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;'>"
            f"{round_labels.get(int(max_r), 'Playoffs')}</span>"
            if max_r and max_r > 0 else
            "<span style='color:rgba(255,255,255,0.15);font-size:10px;'>—</span>"
        )
    else:
        pl_badge = "<span style='color:rgba(255,255,255,0.15);font-size:10px;'>—</span>"

    rows_html += (
        f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
        f'<td style="padding:8px 14px;color:#fff;font-weight:600;font-size:12px;">{r["season_label"]}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{int(r["gamesPlayed"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#5a8f4e;font-size:12px;">{int(r["wins"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#c41e3a;font-size:12px;">{int(r["losses"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{int(r["otLosses"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:{pts_color};font-weight:700;font-size:12px;">{pts_v}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#fff;font-size:12px;">{int(r["goalFor"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{int(r["goalAgainst"])}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:{gd_color};font-family:monospace;font-size:12px;">{gd_str}</td>'
        f'<td style="text-align:center;padding:8px 8px;color:{ptpct_color};font-family:monospace;font-size:12px;">{ptpct:.3f}</td>'
        f'<td style="text-align:center;padding:8px 14px;">{pl_badge}</td>'
        f'</tr>'
    )

st.html(
    '<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
    '<div style="overflow-x:auto;">'
    '<table style="width:100%;border-collapse:collapse;">'
    '<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
    '<th style="text-align:left;padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;white-space:nowrap;">Season</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">GP</th>'
    '<th style="text-align:center;padding:8px 8px;color:#5a8f4e;font-size:10px;font-weight:700;">W</th>'
    '<th style="text-align:center;padding:8px 8px;color:#c41e3a;font-size:10px;font-weight:700;">L</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">OTL</th>'
    '<th style="text-align:center;padding:8px 8px;color:#f97316;font-size:10px;font-weight:700;">PTS</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">GF</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">GA</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">GD</th>'
    '<th style="text-align:center;padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;">Pt%</th>'
    '<th style="text-align:center;padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;">Playoffs</th>'
    f'</tr></thead><tbody>{rows_html}</tbody>'
    '</table></div></div>'
)

data_source_footer("Standings via NHL Stats API · Playoff data 2010–present")
