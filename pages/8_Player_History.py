"""Player History – career trends, arc analysis and 3-season projection."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from lib.db import query_fresh, player_career, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.components import page_header, methodology_note, projection_disclaimer, data_source_footer, zscore_legend

st.set_page_config(page_title="Player History – THA Analytics", layout="wide")
_render_sidebar()

from lib.db import query
from lib.components import tier_badge_html

# ── Load top trending players (cached, shown on landing) ───────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _top_trending() -> pd.DataFrame:
    return query("""
        SELECT DISTINCT CAST(player_id AS VARCHAR) AS player_id,
               player_first_name || ' ' || player_last_name AS name,
               team_abbr, position,
               ROUND(pts_zscore_5v20, 2) AS z,
               ROUND(pts_avg_5g, 2) AS pts5g
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND player_first_name IS NOT NULL
          AND gp_season >= 15
        ORDER BY pts_zscore_5v20 DESC
        LIMIT 10
    """)

df_top = _top_trending()

# ── Header ─────────────────────────────────────────────────────────────────────
page_header("Player History", "Career trends · arc analysis · 3-season projection", data_date=get_data_date())

# ── Top 10 trending quick-select ───────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Top 10 trending right now</p>",
    unsafe_allow_html=True,
)

if not df_top.empty:
    cols = st.columns(min(len(df_top), 5))
    for i, (_, r) in enumerate(df_top.iterrows()):
        col_idx = i % 5
        with cols[col_idx]:
            label = f"{r['name']}  ({r['team_abbr']} · {r['position']})"
            if st.button(
                f"{r['name']}\n{r['team_abbr']} · {r['position']}",
                key=f"top_{r['player_id']}",
                use_container_width=True,
                help=f"PTS/5g: {r['pts5g']}  ·  Form: {r['z']:+.2f}σ",
            ):
                st.session_state["ph_search"] = r["name"]
                st.session_state["ph_selected_id"] = r["player_id"]
                st.rerun()

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

# ── Player search ──────────────────────────────────────────────────────────────
search = st.text_input(
    "",
    placeholder="Search player name (e.g. Erik Karlsson)...",
    label_visibility="collapsed",
    key="ph_search",
)

# Auto-select top trending player if no search and no explicit selection
if (not search or len(search) < 2) and not st.session_state.get("ph_selected_id"):
    if not df_top.empty:
        top = df_top.iloc[0]
        st.session_state["ph_search"] = top["name"]
        st.session_state["ph_selected_id"] = top["player_id"]
        st.rerun()
    else:
        st.info("Enter a player name to explore their full career history.")
        st.stop()

# If we have a directly selected player ID (from top-10 buttons), use it
if st.session_state.get("ph_selected_id") and (not search or len(search) < 2):
    pid = st.session_state["ph_selected_id"]
    try:
        df_direct = query(f"""
            SELECT DISTINCT CAST(player_id AS VARCHAR) AS player_id,
                   player_first_name || ' ' || player_last_name AS name,
                   team_abbr, position
            FROM player_rolling_stats
            WHERE game_recency_rank = 1 AND CAST(player_id AS VARCHAR) = '{pid}'
            LIMIT 1
        """)
        if not df_direct.empty:
            player_row = df_direct.iloc[0]
            player_id = player_row["player_id"]
            player_name = player_row["name"]
            player_pos = player_row["position"]
        else:
            st.stop()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()
else:
    # Sanitise: keep only alphanumeric + spaces
    safe_search = "".join(c for c in search if c.isalnum() or c in " -'.")
    parts = safe_search.strip().split()
    if len(parts) >= 2:
        where_parts = " AND ".join(
            f"LOWER(player_first_name || ' ' || player_last_name) LIKE LOWER('%{p}%')"
            for p in parts
        )
    else:
        where_parts = (
            f"LOWER(player_first_name) LIKE LOWER('%{parts[0]}%')"
            f" OR LOWER(player_last_name) LIKE LOWER('%{parts[0]}%')"
        )

    try:
        df_search = query_fresh(f"""
            SELECT DISTINCT CAST(player_id AS VARCHAR) AS player_id,
                   player_first_name || ' ' || player_last_name AS name,
                   team_abbr, position
            FROM player_rolling_stats
            WHERE game_recency_rank = 1 AND ({where_parts})
            ORDER BY name LIMIT 20
        """)
    except Exception as e:
        st.error(f"Search error: {e}")
        st.stop()

    if df_search.empty:
        st.info("No active players found. Try a different name.")
        st.stop()

    options = {f"{r['name']}  ({r['team_abbr']} · {r['position']})": r for _, r in df_search.iterrows()}
    chosen_label = st.selectbox("", list(options.keys()), label_visibility="collapsed", key="ph_player")
    pr = options[chosen_label]
    player_id = pr["player_id"]
    player_name = pr["name"]
    player_pos = pr["position"]
    # Clear direct-selection so search takes over
    st.session_state.pop("ph_selected_id", None)

# ── Load career data ───────────────────────────────────────────────────────────
try:
    with st.spinner("Loading career data…"):
        df = player_career(player_id)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

if df.empty:
    st.info(f"No regular-season game data found for {player_name}.")
    st.stop()

# ── Derived metrics ────────────────────────────────────────────────────────────
df = df.copy()
df["pts_per_82"]  = df["points"] / df["gp"] * 82
df["goals_per_82"] = df["goals"] / df["gp"] * 82
df["assists_per_82"] = df["assists"] / df["gp"] * 82
# P/60 = total points / total TOI in minutes × 60 = points / (toi_hours*60) × 60 = points / toi_hours
df["p60"]         = df["points"] / df["toi_hours"]
df["season_year"] = df["season"].astype(str).str[:4].astype(int)  # e.g. 20152016 → 2015
df["season_label"] = df["season_year"].astype(str) + "-" + (df["season_year"] + 1).astype(str).str[2:]

# Composite Career Performance Index (CPI):
#   P/60 × (avg_toi_min / position_baseline) × sqrt(gp/82)
# Position baselines: D=25min, C/L/R=19min
toi_baseline = 25.0 if player_pos == "D" else 19.0
df["cpi"] = (
    df["p60"]
    * (df["avg_toi_min"] / toi_baseline).clip(0.5, 1.5)
    * np.sqrt((df["gp"] / 82).clip(0.1, 1.0))
)

# ── Projection (polynomial degree 2) ──────────────────────────────────────────
PROJ_SEASONS = 3
fit_df = df[df["gp"] >= 20].tail(6)  # use up to last 6 healthy seasons for fit
proj_years = []
proj_pts82 = []
proj_cpi = []
proj_upper = []
proj_lower = []

if len(fit_df) >= 3:
    x = fit_df["season_year"].values
    y_pts = fit_df["pts_per_82"].values
    y_cpi = fit_df["cpi"].values

    # Fit degree-2 polynomial (natural aging curve shape)
    coef_pts = np.polyfit(x, y_pts, 2)
    coef_cpi = np.polyfit(x, y_cpi, 2)
    poly_pts = np.poly1d(coef_pts)
    poly_cpi = np.poly1d(coef_cpi)

    # Residual RMSE for confidence band
    resid = y_pts - poly_pts(x)
    rmse = np.sqrt(np.mean(resid**2))

    last_year = int(df["season_year"].iloc[-1])
    for i in range(1, PROJ_SEASONS + 1):
        yr = last_year + i
        proj_years.append(yr)
        p = float(poly_pts(yr))
        c = float(poly_cpi(yr))
        proj_pts82.append(max(p, 0))
        proj_cpi.append(max(c, 0))
        proj_upper.append(max(p + rmse, 0))
        proj_lower.append(max(p - rmse, 0))

has_projection = len(proj_years) > 0

# ── Player section header ──────────────────────────────────────────────────────
seasons_count = len(df)
career_pts = int(df["points"].sum())
career_gp = int(df["gp"].sum())
peak_pts82 = float(df["pts_per_82"].max())
peak_season = df.loc[df["pts_per_82"].idxmax(), "season_label"]
latest_cpi = float(df["cpi"].iloc[-1])

st.markdown(
    f"<h2 style='font-size:22px;font-weight:900;letter-spacing:-0.02em;margin:4px 0 2px;'>{player_name}</h2>"
    f"<p style='color:#8896a8;font-size:13px;margin-bottom:16px;'>"
    f"{player_pos} · {seasons_count} NHL seasons</p>",
    unsafe_allow_html=True,
)

# Career summary bar
st.markdown(
    f"""<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;">
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Career GP</div>
        <div style="color:#fff;font-weight:800;font-size:22px;">{career_gp}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Career PTS</div>
        <div style="color:#5a8f4e;font-weight:800;font-size:22px;">{career_pts}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Peak PTS/82</div>
        <div style="color:#f97316;font-weight:800;font-size:22px;">{peak_pts82:.0f}</div>
        <div style="color:#8896a8;font-size:10px;">{peak_season}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">This season CPI</div>
        <div style="color:#87ceeb;font-weight:800;font-size:22px;">{latest_cpi:.2f}</div>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── Career narrative ──────────────────────────────────────────────────────────
current_pts82 = float(df["pts_per_82"].iloc[-1])
current_season_label = df["season_label"].iloc[-1]
peak_pct = current_pts82 / peak_pts82 * 100 if peak_pts82 > 0 else 0

if peak_pct >= 90:
    form_sentence = f"This season ({current_season_label}) they are producing {current_pts82:.0f} PTS/82 — right at their historical peak."
elif peak_pct >= 70:
    form_sentence = f"This season ({current_season_label}) they are producing {current_pts82:.0f} PTS/82 — {peak_pct:.0f}% of their peak output."
elif peak_pct >= 40:
    form_sentence = f"This season ({current_season_label}) they are producing {current_pts82:.0f} PTS/82, down from a peak of {peak_pts82:.0f} in {peak_season}."
else:
    form_sentence = f"Production this season ({current_pts82:.0f} PTS/82) is well below their career peak of {peak_pts82:.0f} in {peak_season}."

if has_projection:
    next_proj = proj_pts82[0]
    next_label = f"{proj_years[0]}-{str(proj_years[0]+1)[2:]}"
    trend_word = "improve to" if next_proj > current_pts82 else "ease to"
    proj_sentence = f"The model projects {trend_word} {next_proj:.0f} PTS/82 pace in {next_label}."
else:
    proj_sentence = "Insufficient data for multi-season projection."

pos_label = {"C": "centre", "L": "left wing", "R": "right wing", "D": "defenceman"}.get(player_pos, player_pos)
narrative = (
    f"{player_name} is an NHL {pos_label} with {seasons_count} regular-season campaigns, "
    f"accumulating {career_pts} career points in {career_gp} games. "
    f"{form_sentence} {proj_sentence}"
)
st.markdown(
    f"<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);"
    f"border-radius:5px;padding:14px 18px;margin-bottom:20px;'>"
    f"<p style='color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;"
    f"letter-spacing:0.06em;margin-bottom:6px;'>Career Summary</p>"
    f"<p style='color:#e0e8f0;font-size:13px;line-height:1.6;margin:0;'>{narrative}</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSITE CAREER ARC (full width)
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(
    "<p style='font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;"
    "color:#8896a8;margin-bottom:6px;'>Career Performance Arc  ·  CPI = P/60 × deployment × durability</p>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='font-size:11px;color:#8896a8;margin-bottom:12px;'>"
    "CPI (Career Performance Index) combines points-per-60-minutes with positional deployment and game availability. "
    "Dashed line = polynomial projection, shaded band = ±1 RMSE confidence.</p>",
    unsafe_allow_html=True,
)

fig_arc = go.Figure()

# Historical CPI area
fig_arc.add_trace(go.Scatter(
    x=df["season_label"], y=df["cpi"],
    name="CPI (actual)",
    mode="lines+markers",
    line=dict(color="#5a8f4e", width=2.5),
    marker=dict(size=7, color="#5a8f4e", line=dict(width=1.5, color="#fff")),
    fill="tozeroy",
    fillcolor="rgba(90,143,78,0.08)",
    hovertemplate="<b>%{x}</b><br>CPI: %{y:.2f}<extra></extra>",
))

# Projected CPI
if has_projection:
    proj_labels = [f"{y}-{str(y+1)[2:]}" for y in proj_years]
    fig_arc.add_trace(go.Scatter(
        x=proj_labels, y=proj_cpi,
        name="Projection",
        mode="lines+markers",
        line=dict(color="#5a8f4e", width=2, dash="dash"),
        marker=dict(size=6, color="#5a8f4e", symbol="circle-open"),
        hovertemplate="<b>%{x}</b><br>Projected CPI: %{y:.2f}<extra></extra>",
    ))

fig_arc.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#8896a8", font_size=11,
    margin=dict(l=0, r=0, t=10, b=30),
    height=200,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(type="category", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10), title="CPI"),
)
st.plotly_chart(fig_arc, use_container_width=True, config={"displayModeBar": False})
projection_disclaimer()

# ═══════════════════════════════════════════════════════════════════════════════
# SUBTABS
# ═══════════════════════════════════════════════════════════════════════════════
tab_pts, tab_toi, tab_eff, tab_table = st.tabs(
    ["Points", "Ice Time", "Efficiency (P/60)", "Season Table"]
)

_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#8896a8", font_size=11,
    margin=dict(l=0, r=0, t=20, b=30),
    height=260,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(type="category", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10), tickangle=-35),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
)

# ── Tab: Points ───────────────────────────────────────────────────────────────
with tab_pts:
    fig_pts = go.Figure()

    # Stacked G/A bars
    fig_pts.add_trace(go.Bar(
        x=df["season_label"], y=df["goals"],
        name="Goals", marker_color="#c41e3a", opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Goals: %{y:.0f}<extra></extra>",
    ))
    fig_pts.add_trace(go.Bar(
        x=df["season_label"], y=df["assists"],
        name="Assists", marker_color="#87ceeb", opacity=0.7,
        hovertemplate="<b>%{x}</b><br>Assists: %{y:.0f}<extra></extra>",
    ))

    # PTS/82 line on secondary axis
    if has_projection:
        proj_labels = [f"{y}-{str(y+1)[2:]}" for y in proj_years]
        x_all = list(df["season_label"]) + proj_labels
        y_pts82_all = list(df["pts_per_82"]) + proj_pts82

        # Confidence band (projected portion only)
        fig_pts.add_trace(go.Scatter(
            x=proj_labels + proj_labels[::-1],
            y=proj_upper + proj_lower[::-1],
            fill="toself", fillcolor="rgba(249,115,22,0.08)",
            line=dict(color="rgba(249,115,22,0)"),
            showlegend=False, hoverinfo="skip",
        ))
        fig_pts.add_trace(go.Scatter(
            x=proj_labels, y=proj_pts82,
            name="Projected PTS/82",
            mode="lines+markers",
            line=dict(color="#f97316", width=1.8, dash="dash"),
            marker=dict(size=5, color="#f97316", symbol="circle-open"),
            yaxis="y2",
            hovertemplate="<b>%{x}</b><br>Projected: %{y:.0f} PTS/82<extra></extra>",
        ))

    fig_pts.add_trace(go.Scatter(
        x=df["season_label"], y=df["pts_per_82"],
        name="PTS/82",
        mode="lines+markers",
        line=dict(color="#f97316", width=2),
        marker=dict(size=6, color="#f97316"),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>PTS/82: %{y:.0f}<extra></extra>",
    ))

    layout_pts = dict(**_CHART_LAYOUT)
    layout_pts["barmode"] = "stack"
    layout_pts["yaxis2"] = dict(
        overlaying="y", side="right",
        gridcolor="rgba(255,255,255,0)", tickfont=dict(size=10, color="#f97316"),
        title="PTS/82",
    )
    layout_pts["yaxis"]["title"] = "G + A"
    fig_pts.update_layout(**layout_pts)
    st.plotly_chart(fig_pts, use_container_width=True, config={"displayModeBar": False})

    # GP bar below
    fig_gp = go.Figure(go.Bar(
        x=df["season_label"], y=df["gp"],
        marker_color=[
            "#5a8f4e" if g >= 70 else ("#f97316" if g >= 50 else "#c41e3a")
            for g in df["gp"]
        ],
        opacity=0.75,
        hovertemplate="<b>%{x}</b><br>GP: %{y}<extra></extra>",
    ))
    fig_gp.add_hline(y=82, line_dash="dot", line_color="rgba(255,255,255,0.15)")
    gp_layout = {**_CHART_LAYOUT}
    gp_layout["height"] = 100
    gp_layout["showlegend"] = False
    gp_layout["margin"] = dict(l=0, r=0, t=4, b=30)
    gp_layout["xaxis"] = dict(type="category", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9), tickangle=-35)
    gp_layout["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9), range=[0, 90], title="GP")
    fig_gp.update_layout(**gp_layout)
    st.plotly_chart(fig_gp, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        "<p style='color:#8896a8;font-size:10px;margin-top:-8px;'>"
        "Green = 70+ GP · Orange = 50–69 GP · Red = &lt;50 GP (injury/shortened season)</p>",
        unsafe_allow_html=True,
    )

# ── Tab: Ice Time ─────────────────────────────────────────────────────────────
with tab_toi:
    fig_toi = go.Figure()
    fig_toi.add_trace(go.Scatter(
        x=df["season_label"], y=df["avg_toi_min"],
        name="Avg TOI / game",
        mode="lines+markers",
        line=dict(color="#87ceeb", width=2.5),
        marker=dict(size=7, color="#87ceeb", line=dict(width=1.5, color="#fff")),
        fill="tozeroy", fillcolor="rgba(135,206,235,0.06)",
        hovertemplate="<b>%{x}</b><br>TOI: %{y:.1f} min/game<extra></extra>",
    ))
    # Position reference line
    fig_toi.add_hline(
        y=toi_baseline,
        line_dash="dot", line_color="rgba(255,255,255,0.18)",
        annotation_text=f"Pos. avg ({toi_baseline:.0f}min)",
        annotation_font_size=10,
        annotation_font_color="#8896a8",
    )
    layout_toi = dict(**_CHART_LAYOUT)
    layout_toi["yaxis"]["title"] = "Minutes / game"
    fig_toi.update_layout(**layout_toi)
    st.plotly_chart(fig_toi, use_container_width=True, config={"displayModeBar": False})

    # Total TOI hours
    fig_toi_h = go.Figure(go.Bar(
        x=df["season_label"], y=df["toi_hours"].round(1),
        name="Total TOI (hours)", marker_color="#87ceeb", opacity=0.5,
        hovertemplate="<b>%{x}</b><br>Total TOI: %{y:.1f}h<extra></extra>",
    ))
    toi_h_layout = {**_CHART_LAYOUT}
    toi_h_layout["height"] = 100
    toi_h_layout["showlegend"] = False
    toi_h_layout["margin"] = dict(l=0, r=0, t=4, b=30)
    toi_h_layout["xaxis"] = dict(type="category", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9), tickangle=-35)
    toi_h_layout["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9), title="Hours")
    fig_toi_h.update_layout(**toi_h_layout)
    st.plotly_chart(fig_toi_h, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f"<p style='color:#8896a8;font-size:10px;margin-top:-8px;'>"
        f"Dotted line = positional deployment baseline ({toi_baseline:.0f} min/game for {player_pos})</p>",
        unsafe_allow_html=True,
    )

# ── Tab: Efficiency P/60 ──────────────────────────────────────────────────────
with tab_eff:
    fig_eff = make_subplots(specs=[[{"secondary_y": True}]])

    fig_eff.add_trace(go.Scatter(
        x=df["season_label"], y=df["p60"].round(2),
        name="P/60",
        mode="lines+markers",
        line=dict(color="#5a8f4e", width=2.5),
        marker=dict(size=7, color="#5a8f4e", line=dict(width=1.5, color="#fff")),
        fill="tozeroy", fillcolor="rgba(90,143,78,0.08)",
        hovertemplate="<b>%{x}</b><br>P/60: %{y:.2f}<extra></extra>",
    ), secondary_y=False)

    fig_eff.add_trace(go.Scatter(
        x=df["season_label"], y=(df["goals"] / df["toi_hours"]).round(2),
        name="G/60",
        mode="lines",
        line=dict(color="#c41e3a", width=1.5, dash="dot"),
        hovertemplate="<b>%{x}</b><br>G/60: %{y:.2f}<extra></extra>",
    ), secondary_y=True)

    fig_eff.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8896a8", font_size=11,
        margin=dict(l=0, r=0, t=20, b=30),
        height=260,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(type="category", gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10), tickangle=-35),
    )
    fig_eff.update_yaxes(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10),
                          title_text="P/60", secondary_y=False)
    fig_eff.update_yaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=10, color="#c41e3a"),
                          title_text="G/60", secondary_y=True)
    st.plotly_chart(fig_eff, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        "<p style='color:#8896a8;font-size:11px;'>"
        "<b style='color:#fff;'>P/60</b> (Points per 60 minutes) is the industry-standard efficiency metric — "
        "it normalises production for ice time, enabling fair comparison across eras and deployment levels. "
        "Elite forwards typically exceed 2.5 P/60; elite defencemen above 1.5.</p>",
        unsafe_allow_html=True,
    )

# ── Tab: Season Table ─────────────────────────────────────────────────────────
with tab_table:
    rows = ""
    for _, r in df.sort_values("season_year", ascending=False).iterrows():
        p60_val = float(r["p60"])
        p60_color = "#f97316" if p60_val >= 2.5 else ("#5a8f4e" if p60_val >= 1.5 else "#8896a8")
        cpi_val = float(r["cpi"])
        gp_val = int(r["gp"])
        gp_color = "#5a8f4e" if gp_val >= 70 else ("#f97316" if gp_val >= 50 else "#c41e3a")
        rows += (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<td style="padding:8px 14px;color:#fff;font-weight:600;font-size:12px;">{r["season_label"]}</td>'
            f'<td style="padding:8px 8px;color:{gp_color};font-size:12px;text-align:center;">{gp_val}</td>'
            f'<td style="padding:8px 8px;color:#fff;font-size:12px;text-align:center;">{int(r["goals"])}</td>'
            f'<td style="padding:8px 8px;color:#8896a8;font-size:12px;text-align:center;">{int(r["assists"])}</td>'
            f'<td style="padding:8px 8px;color:#5a8f4e;font-weight:700;font-size:12px;text-align:center;">{int(r["points"])}</td>'
            f'<td style="padding:8px 8px;color:#f97316;font-size:12px;text-align:center;">{r["pts_per_82"]:.0f}</td>'
            f'<td style="padding:8px 8px;color:#87ceeb;font-size:12px;text-align:center;">{r["avg_toi_min"]:.1f}</td>'
            f'<td style="padding:8px 8px;color:{p60_color};font-family:monospace;font-weight:700;font-size:12px;text-align:center;">{p60_val:.2f}</td>'
            f'<td style="padding:8px 14px;color:#8896a8;font-family:monospace;font-size:12px;text-align:center;">{cpi_val:.2f}</td>'
            f'</tr>'
        )

    # Projection rows
    if has_projection:
        proj_labels = [f"{y}-{str(y+1)[2:]}" for y in proj_years]
        for i, lbl in enumerate(proj_labels):
            p_val = proj_pts82[i]
            c_val = proj_cpi[i]
            rows += (
                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);'
                f'background:rgba(90,143,78,0.04);opacity:0.7;">'
                f'<td style="padding:8px 14px;color:#5a8f4e;font-style:italic;font-size:12px;">'
                f'{lbl} <span style="font-size:10px;color:#5a8f4e33;">(proj)</span></td>'
                f'<td colspan="4" style="padding:8px 8px;color:#8896a8;font-size:11px;text-align:center;">—</td>'
                f'<td style="padding:8px 8px;color:#5a8f4e;font-size:12px;text-align:center;font-style:italic;">{p_val:.0f}</td>'
                f'<td style="padding:8px 8px;color:#8896a8;text-align:center;">—</td>'
                f'<td style="padding:8px 8px;color:#8896a8;text-align:center;">—</td>'
                f'<td style="padding:8px 14px;color:#5a8f4e;font-style:italic;text-align:center;">{c_val:.2f}</td>'
                f'</tr>'
            )

    st.html(
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'<th style="padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">Season</th>'
        f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">GP</th>'
        f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">G</th>'
        f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">A</th>'
        f'<th style="padding:8px 8px;color:#5a8f4e;font-size:10px;font-weight:700;text-align:center;">PTS</th>'
        f'<th style="padding:8px 8px;color:#f97316;font-size:10px;font-weight:600;text-align:center;">PTS/82</th>'
        f'<th style="padding:8px 8px;color:#87ceeb;font-size:10px;font-weight:600;text-align:center;">TOI/g</th>'
        f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:700;text-align:center;">P/60</th>'
        f'<th style="padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">CPI</th>'
        f'</tr></thead><tbody>{rows}</tbody>'
        f'</table></div>'
    )

    st.markdown(
        "<p style='color:#8896a8;font-size:10px;margin-top:8px;'>"
        "PTS/82 = points pace over full 82-game season · "
        "P/60 = points per 60 min TOI (efficiency) · "
        "CPI = composite index (P/60 × deployment × durability). "
        "Projected rows use polynomial regression on last 6 healthy seasons.</p>",
        unsafe_allow_html=True,
    )

data_source_footer()
