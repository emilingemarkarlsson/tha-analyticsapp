"""Goalies page – form table, career arc and season-by-season stats."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, data_source_footer, zscore_legend

st.set_page_config(page_title="Goalies – THA Analytics", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

page_header("Goalies", "Current season form · Sv% z-score vs 20-game baseline", data_date=get_data_date())
zscore_legend()

# ── Top trending goalies ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _top_goalies() -> pd.DataFrame:
    return query("""
        SELECT CAST(player_id AS VARCHAR) AS player_id,
               player_first_name || ' ' || player_last_name AS name,
               team_abbr,
               ROUND(sv_pct_avg_5g * 100, 2) AS sv5g,
               ROUND(sv_pct_zscore_5v20, 2) AS z
        FROM goalie_rolling_stats
        WHERE game_recency_rank = 1
          AND gp_season >= 8
          AND player_first_name IS NOT NULL
        ORDER BY sv_pct_zscore_5v20 DESC
        LIMIT 10
    """)

df_top = _top_goalies()

st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Top performing right now</p>",
    unsafe_allow_html=True,
)

if not st.session_state.get("go_selected_id") and not df_top.empty:
    st.session_state["go_selected_id"] = df_top.iloc[0]["player_id"]

if not df_top.empty:
    cols = st.columns(min(len(df_top), 5))
    for i, (_, r) in enumerate(df_top.iterrows()):
        with cols[i % 5]:
            is_active = st.session_state.get("go_selected_id") == r["player_id"]
            if st.button(
                f"{r['name']}\n{r['team_abbr']}",
                key=f"gtop_{r['player_id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                help=f"Sv%/5g: {r['sv5g']:.2f}  ·  Form: {r['z']:+.2f}σ",
            ):
                st.session_state["go_selected_id"] = r["player_id"]
                st.rerun()

st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

# ── Current season table ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _goalie_table() -> pd.DataFrame:
    return query("""
        SELECT CAST(gr.player_id AS VARCHAR) AS player_id,
               gr.player_first_name || ' ' || gr.player_last_name AS name,
               gr.team_abbr,
               gr.gp_season AS gp,
               gs.wins, gs.losses, gs.otLosses,
               ROUND(gs.savePct * 100, 2) AS sv_pct,
               ROUND(gs.goalsAgainstAverage, 2) AS gaa,
               gs.shutouts,
               ROUND(gr.sv_pct_avg_5g * 100, 2) AS sv_5g,
               ROUND(gr.sv_pct_avg_20g * 100, 2) AS sv_20g,
               ROUND(gr.sv_pct_zscore_5v20, 2) AS z
        FROM goalie_rolling_stats gr
        LEFT JOIN goalie_stats gs
               ON gs.playerId = gr.player_id
              AND gs.season = gr.season
        WHERE gr.game_recency_rank = 1
          AND gr.gp_season >= 5
          AND gr.player_first_name IS NOT NULL
        ORDER BY gr.sv_pct_zscore_5v20 DESC
    """)

df_table = _goalie_table()

# ── Search ─────────────────────────────────────────────────────────────────────
search = st.text_input(
    "", placeholder="Search goalie name...",
    label_visibility="collapsed", key="go_search",
)
if search and len(search) >= 2:
    st.session_state.pop("go_selected_id", None)

# ── Resolve selected goalie ────────────────────────────────────────────────────
if st.session_state.get("go_selected_id") and (not search or len(search) < 2):
    gid = st.session_state["go_selected_id"]
    row_match = df_table[df_table["player_id"] == gid]
    if not row_match.empty:
        goalie_id   = gid
        goalie_name = row_match.iloc[0]["name"]
    else:
        goalie_id = goalie_name = None
else:
    safe = "".join(c for c in search if c.isalnum() or c in " -'.")
    parts = safe.strip().split()
    if len(parts) >= 2:
        where = " AND ".join(
            f"LOWER(player_first_name || ' ' || player_last_name) LIKE LOWER('%{p}%')"
            for p in parts
        )
    else:
        where = (
            f"LOWER(player_first_name) LIKE LOWER('%{parts[0]}%')"
            f" OR LOWER(player_last_name) LIKE LOWER('%{parts[0]}%')"
        ) if parts else "1=0"

    df_search = query_fresh(f"""
        SELECT DISTINCT CAST(player_id AS VARCHAR) AS player_id,
               player_first_name || ' ' || player_last_name AS name
        FROM goalie_rolling_stats
        WHERE game_recency_rank = 1 AND ({where})
        ORDER BY name LIMIT 20
    """)

    if df_search.empty:
        st.info("No goalies found.")
        st.stop()

    options = {f"{r['name']}": r for _, r in df_search.iterrows()}
    chosen = st.selectbox("", list(options.keys()), label_visibility="collapsed", key="go_player")
    pr = options[chosen]
    goalie_id   = pr["player_id"]
    goalie_name = pr["name"]
    st.session_state.pop("go_selected_id", None)

if not goalie_id:
    st.stop()

# ── Load career + bio ──────────────────────────────────────────────────────────
try:
    with st.spinner("Loading…"):
        df_career = query_fresh(f"""
            SELECT season, gamesPlayed AS gp, wins, losses, otLosses,
                   ROUND(savePct * 100, 3) AS sv_pct,
                   ROUND(goalsAgainstAverage, 2) AS gaa,
                   shutouts,
                   ROUND(saves * 100.0 / NULLIF(shotsAgainst, 0), 2) AS sv_check
            FROM goalie_stats
            WHERE playerId = {goalie_id}
            ORDER BY season
        """)
        df_bio = query_fresh(f"""
            SELECT firstName, lastName, positionCode, sweaterNumber,
                   heightInCentimeters, weightInKilograms,
                   birthDate, birthCity, birthCountry, headshot
            FROM players WHERE id = {goalie_id} LIMIT 1
        """)
        df_form = query_fresh(f"""
            SELECT sv_pct_avg_5g, sv_pct_avg_20g, sv_pct_zscore_5v20,
                   ga_avg_5g, gp_season, saves_season, shots_against_season
            FROM goalie_rolling_stats
            WHERE player_id = {goalie_id} AND game_recency_rank = 1
            LIMIT 1
        """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

if df_career.empty:
    st.info(f"No career data found for {goalie_name}.")
    st.stop()

# Season label helper
df_career = df_career.copy()
df_career["season_year"]  = df_career["season"].astype(str).str[:4].astype(int)
df_career["season_label"] = df_career["season_year"].astype(str) + "-" + (df_career["season_year"] + 1).astype(str).str[2:]

# ── Header ─────────────────────────────────────────────────────────────────────
seasons_count = len(df_career)
career_gp     = int(df_career["gp"].sum())
career_wins   = int(df_career["wins"].sum())
peak_sv       = float(df_career["sv_pct"].max())
peak_sv_lbl   = df_career.loc[df_career["sv_pct"].idxmax(), "season_label"]

st.markdown(
    f"<h2 style='font-size:22px;font-weight:900;letter-spacing:-0.02em;margin:4px 0 2px;'>"
    f"{goalie_name}</h2>"
    f"<p style='color:#8896a8;font-size:13px;margin-bottom:12px;'>"
    f"G · {seasons_count} NHL seasons</p>",
    unsafe_allow_html=True,
)

# Bio card
if not df_bio.empty:
    b = df_bio.iloc[0]
    height_cm = int(b["heightInCentimeters"]) if b["heightInCentimeters"] else 0
    weight_kg = int(b["weightInKilograms"])   if b["weightInKilograms"]   else 0
    feet, inches = divmod(round(height_cm / 2.54), 12)
    lbs     = round(weight_kg * 2.205)
    birth   = str(b["birthDate"])[:10] if b["birthDate"] else "—"
    city    = b["birthCity"]    or ""
    country = b["birthCountry"] or ""
    num     = int(b["sweaterNumber"]) if b["sweaterNumber"] else 0
    headshot = str(b["headshot"]) if b["headshot"] else ""
    bio_line = f"#{num} · {feet}'{inches}\" · {lbs} lbs · Born {birth}"
    if city or country:
        bio_line += f" · {city}, {country}"

    img_html = (
        f'<img src="{headshot}" style="width:72px;height:72px;border-radius:50%;'
        f'object-fit:cover;border:2px solid rgba(90,143,78,0.4);" onerror="this.style.display=\'none\'">'
        if headshot else
        f'<div style="width:72px;height:72px;border-radius:50%;background:#5a8f4e;'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-weight:900;font-size:24px;color:#fff;">{goalie_name[0]}</div>'
    )
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:16px;
                        background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);
                        border-radius:6px;padding:12px 16px;margin-bottom:16px;max-width:520px;">
          {img_html}
          <div>
            <div style="color:#fff;font-weight:700;font-size:15px;margin-bottom:2px;">{goalie_name}</div>
            <div style="color:#5a8f4e;font-size:11px;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.06em;margin-bottom:4px;">Goalie · {country}</div>
            <div style="color:#8896a8;font-size:11px;line-height:1.6;">{bio_line}</div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

# Career summary
st.markdown(
    f"""<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Career GP</div>
        <div style="color:#fff;font-weight:800;font-size:22px;">{career_gp}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Career Wins</div>
        <div style="color:#5a8f4e;font-weight:800;font-size:22px;">{career_wins}</div>
      </div>
      <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                  border-radius:5px;padding:10px 18px;">
        <div style="color:#8896a8;font-size:10px;text-transform:uppercase;letter-spacing:0.06em;">Peak Sv%</div>
        <div style="color:#f97316;font-weight:800;font-size:22px;">{peak_sv:.1f}<span style="font-size:12px;font-weight:400;">%</span></div>
        <div style="color:#8896a8;font-size:10px;">{peak_sv_lbl}</div>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── Current form metrics ───────────────────────────────────────────────────────
if not df_form.empty:
    f_row = df_form.iloc[0]
    fz    = float(f_row["sv_pct_zscore_5v20"])
    fz_color = "#f97316" if fz >= 0 else "#87ceeb"
    fz_str   = f"+{fz:.2f}σ" if fz >= 0 else f"{fz:.2f}σ"
    sv5  = float(f_row["sv_pct_avg_5g"]) * 100
    sv20 = float(f_row["sv_pct_avg_20g"]) * 100
    gaa5 = float(f_row["ga_avg_5g"])
    gp_s = int(f_row["gp_season"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Form (σ)", fz_str, "5g vs 20g Sv%")
    with c2:
        st.metric("Sv% / 5g", f"{sv5:.2f}%", f"20g avg: {sv20:.2f}%")
    with c3:
        st.metric("GAA / 5g", f"{gaa5:.2f}", "Goals against avg")
    with c4:
        st.metric("GP this season", gp_s)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ── Save% arc chart ────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8896a8", size=11),
    margin=dict(l=0, r=0, t=30, b=10),
    height=220,
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10)),
    hoverlabel=dict(bgcolor="#1a1a2e", bordercolor="rgba(255,255,255,0.1)", font_color="#f1f5f9"),
)

sv_vals = df_career["sv_pct"].values
league_avg = 90.0  # approximate NHL average

fig_sv = go.Figure()
fig_sv.add_hrect(y0=91.5, y1=94, fillcolor="rgba(90,143,78,0.05)", line_width=0,
                 annotation_text="Elite (91.5%+)", annotation_font_color="#5a8f4e",
                 annotation_font_size=9, annotation_position="top left")
fig_sv.add_hline(y=league_avg, line_dash="dot", line_color="rgba(255,255,255,0.2)",
                 annotation_text="League avg", annotation_font_size=9,
                 annotation_font_color="rgba(255,255,255,0.4)", annotation_position="top right")

fig_sv.add_trace(go.Scatter(
    x=df_career["season_label"],
    y=sv_vals,
    mode="lines+markers",
    line=dict(color="#5a8f4e", width=2.5),
    marker=dict(size=6, color=["#f97316" if v == sv_vals.max() else "#5a8f4e" for v in sv_vals]),
    fill="tozeroy",
    fillcolor="rgba(90,143,78,0.06)",
    hovertemplate="<b>%{x}</b><br>Sv%: %{y:.2f}%<extra></extra>",
))

peak_idx = list(sv_vals).index(sv_vals.max())
fig_sv.add_annotation(
    x=df_career["season_label"].iloc[peak_idx],
    y=sv_vals.max(),
    text=f"Career best<br>{sv_vals.max():.2f}%",
    showarrow=True, arrowhead=0, arrowcolor="rgba(255,255,255,0.2)",
    font=dict(size=9, color="#f97316"), bgcolor="rgba(0,0,0,0.6)",
    bordercolor="rgba(249,115,22,0.3)", borderwidth=1, borderpad=3, ay=-30,
)

layout = dict(**CHART_LAYOUT)
layout["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=10),
                       title="Sv%", range=[min(sv_vals) - 1, max(sv_vals) + 1])
fig_sv.update_layout(**layout)
fig_sv.update_xaxes(type="category")

st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:16px 0 4px;'>Save % Arc</p>",
    unsafe_allow_html=True,
)
st.plotly_chart(fig_sv, use_container_width=True, config={"displayModeBar": False})

# ── Career table ───────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin:20px 0 6px;'>Season by Season</p>",
    unsafe_allow_html=True,
)

rows = ""
for _, r in df_career.sort_values("season_year", ascending=False).iterrows():
    sv = float(r["sv_pct"])
    sv_color = "#f97316" if sv >= 92.0 else ("#5a8f4e" if sv >= 91.0 else ("#8896a8" if sv >= 89.5 else "#87ceeb"))
    gaa = float(r["gaa"])
    gaa_color = "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")
    gp = int(r["gp"])
    w  = int(r["wins"])  if pd.notna(r["wins"])     else 0
    l  = int(r["losses"]) if pd.notna(r["losses"])  else 0
    otl = int(r["otLosses"]) if pd.notna(r["otLosses"]) else 0
    so  = int(r["shutouts"]) if pd.notna(r["shutouts"]) else 0
    rows += (
        f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
        f'<td style="padding:8px 14px;color:#fff;font-weight:600;font-size:12px;">{r["season_label"]}</td>'
        f'<td style="padding:8px 8px;color:#8896a8;font-size:12px;text-align:center;">{gp}</td>'
        f'<td style="padding:8px 8px;color:#5a8f4e;font-weight:700;font-size:12px;text-align:center;">{w}</td>'
        f'<td style="padding:8px 8px;color:#c41e3a;font-size:12px;text-align:center;">{l}</td>'
        f'<td style="padding:8px 8px;color:#8896a8;font-size:12px;text-align:center;">{otl}</td>'
        f'<td style="padding:8px 8px;color:{sv_color};font-family:monospace;font-weight:700;font-size:12px;text-align:center;">{sv:.2f}%</td>'
        f'<td style="padding:8px 8px;color:{gaa_color};font-family:monospace;font-size:12px;text-align:center;">{gaa:.2f}</td>'
        f'<td style="padding:8px 14px;color:#8896a8;font-size:12px;text-align:center;">{so}</td>'
        f'</tr>'
    )

st.html(
    f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
    f'<table style="width:100%;border-collapse:collapse;">'
    f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
    f'<th style="padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">Season</th>'
    f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">GP</th>'
    f'<th style="padding:8px 8px;color:#5a8f4e;font-size:10px;font-weight:700;text-align:center;">W</th>'
    f'<th style="padding:8px 8px;color:#c41e3a;font-size:10px;font-weight:600;text-align:center;">L</th>'
    f'<th style="padding:8px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">OTL</th>'
    f'<th style="padding:8px 8px;color:#f97316;font-size:10px;font-weight:700;text-align:center;">Sv%</th>'
    f'<th style="padding:8px 8px;color:#87ceeb;font-size:10px;font-weight:600;text-align:center;">GAA</th>'
    f'<th style="padding:8px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">SO</th>'
    f'</tr></thead><tbody>{rows}</tbody>'
    f'</table></div>'
)

st.markdown(
    "<p style='color:#8896a8;font-size:10px;margin-top:8px;'>"
    "Sv% = save percentage · GAA = goals against average · SO = shutouts · "
    "Form (σ) = last 5 games vs 20-game Sv% baseline</p>",
    unsafe_allow_html=True,
)

data_source_footer()
