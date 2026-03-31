"""THA Terminal – Börsdata-style hockey analytics terminal."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login

st.set_page_config(page_title="Terminal – THA Analytics", layout="wide")
_render_sidebar()
require_login()

# ══════════════════════════════════════════════════════════════════════════════
#  CSS – terminal density
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
[data-testid="block-container"] { padding-top:0.6rem !important; padding-bottom:0 !important; }
[data-testid="stHorizontalBlock"] { gap:0 !important; }

/* Compact dataframe for left panel */
[data-testid="stDataFrame"] thead th {
    font-size:9px !important; text-transform:uppercase; letter-spacing:0.06em;
    background:rgba(255,255,255,0.04) !important; padding:4px 8px !important;
    color:#8896a8 !important;
}
[data-testid="stDataFrame"] tbody td {
    font-size:11px !important; padding:3px 8px !important;
    font-family:'SF Mono','Fira Code',monospace !important;
}
[data-testid="stDataFrame"] tbody tr { height:26px !important; }
[data-testid="stDataFrame"] tbody tr:hover td { background:rgba(90,143,78,0.08) !important; }

/* Remove expander arrow style */
details summary { padding:4px 0 !important; }

/* Tighter metric cards */
[data-testid="stMetric"] { padding:0 !important; }
[data-testid="stMetricValue"] { font-size:1.2rem !important; }
[data-testid="stMetricLabel"] { font-size:10px !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  STATE
# ══════════════════════════════════════════════════════════════════════════════
def _ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

_ss("t_mode",   "Skaters")   # Skaters | Goalies | Teams
_ss("t_tab",    "Overview")  # Overview | Form | Career | Splits
_ss("t_filter", "All")       # division/position/preset chip
_ss("t_id",     None)        # selected player_id or team_abbr
_ss("t_search", "")

DIV_TEAMS = {
    "ATL": ["TBL","BUF","MTL","BOS","OTT","DET","TOR","FLA"],
    "MET": ["CAR","NYI","CBJ","PIT","PHI","WSH","NJD","NYR"],
    "CEN": ["COL","DAL","MIN","UTA","NSH","WPG","STL","CHI"],
    "PAC": ["ANA","EDM","VGK","LAK","SEA","SJS","CGY","VAN"],
}
EAST_TEAMS = DIV_TEAMS["ATL"] + DIV_TEAMS["MET"]
WEST_TEAMS = DIV_TEAMS["CEN"] + DIV_TEAMS["PAC"]

# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner=False)
def _skater_list() -> pd.DataFrame:
    return query("""
        SELECT CAST(pr.player_id AS VARCHAR) AS pid,
               pr.player_first_name || ' ' || pr.player_last_name AS name,
               pr.team_abbr AS team,
               pr.position AS pos,
               pr.gp_season AS gp,
               CAST(pr.goals_season AS INTEGER) AS g,
               CAST(pr.assists_season AS INTEGER) AS a,
               CAST(pr.pts_season AS INTEGER) AS pts,
               ROUND(pr.pts_avg_5g, 2) AS avg5,
               ROUND(pr.pts_zscore_5v20, 2) AS z,
               ss.plusMinus AS pm,
               ss.ppPoints AS ppp,
               ROUND(ss.shootingPct*100,1) AS sh_pct,
               ROUND(ss.faceoffWinPct*100,1) AS fo_pct,
               ROUND(pr.toi_avg_10g/60.0, 1) AS toi
        FROM player_rolling_stats pr
        LEFT JOIN skater_stats ss ON ss.playerId = pr.player_id AND ss.season = pr.season
        WHERE pr.game_recency_rank = 1
          AND pr.season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND pr.gp_season >= 5
          AND pr.player_first_name IS NOT NULL
        ORDER BY pr.pts_zscore_5v20 DESC
    """)

@st.cache_data(ttl=900, show_spinner=False)
def _goalie_list() -> pd.DataFrame:
    return query("""
        SELECT CAST(gr.player_id AS VARCHAR) AS pid,
               gr.player_first_name || ' ' || gr.player_last_name AS name,
               gr.team_abbr AS team,
               gr.gp_season AS gp,
               gs.wins AS w,
               ROUND(gs.savePct*100, 2) AS sv_pct,
               ROUND(gs.goalsAgainstAverage, 2) AS gaa,
               gs.shutouts AS so,
               ROUND(gr.sv_pct_avg_5g*100, 2) AS sv5,
               ROUND(gr.sv_pct_zscore_5v20, 2) AS z
        FROM goalie_rolling_stats gr
        LEFT JOIN goalie_stats gs ON gs.playerId = gr.player_id AND gs.season = gr.season
        WHERE gr.game_recency_rank = 1
          AND gr.gp_season >= 3
          AND gr.player_first_name IS NOT NULL
        ORDER BY gr.sv_pct_zscore_5v20 DESC
    """)

@st.cache_data(ttl=900, show_spinner=False)
def _team_list() -> pd.DataFrame:
    return query("""
        SELECT st.teamAbbrev AS abbr,
               st.divisionAbbrev AS div,
               st.conferenceAbbrev AS conf,
               st.gamesPlayed AS gp,
               st.wins AS w, st.losses AS l, st.otLosses AS otl,
               st.points AS pts,
               (st.goalFor - st.goalAgainst) AS diff,
               ROUND(ts.powerPlayPct*100,1) AS pp_pct,
               ROUND(ts.penaltyKillPct*100,1) AS pk_pct,
               ROUND(ts.shotsForPerGame,1) AS sf,
               ROUND(tr.pts_zscore_5v20, 2) AS z,
               ROUND(tr.gf_avg_10g, 2) AS gf10,
               ROUND(tr.ga_avg_10g, 2) AS ga10
        FROM standings st
        LEFT JOIN team_stats ts ON ts.teamFullName=st.teamName AND ts.season=st.season
        LEFT JOIN team_rolling_stats tr ON tr.team_abbr=st.teamAbbrev AND tr.game_recency_rank=1
        WHERE st.season=(SELECT MAX(season) FROM standings)
        ORDER BY st.points DESC
    """)

@st.cache_data(ttl=1800, show_spinner=False)
def _player_bio(pid) -> pd.Series | None:
    df = query_fresh(f"SELECT * FROM players WHERE id={pid} LIMIT 1")
    return df.iloc[0] if not df.empty else None

@st.cache_data(ttl=600, show_spinner=False)
def _player_games(pid) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT g.game_date AS date,
               pgs.goals AS G, pgs.assists AS A,
               pgs.goals+pgs.assists AS PTS,
               ROUND(pgs.toi_seconds/60.0,1) AS TOI
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id=g.game_id
        WHERE pgs.player_id={pid} AND g.game_type=2
          AND g.season=(SELECT MAX(season) FROM games WHERE game_type='2')
        ORDER BY g.game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=600, show_spinner=False)
def _player_form_series(pid) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT g.game_date AS date,
               pgs.goals+pgs.assists AS pts
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id=g.game_id
        WHERE pgs.player_id={pid} AND g.game_type=2
          AND g.season=(SELECT MAX(season) FROM games WHERE game_type='2')
        ORDER BY g.game_date
    """)

@st.cache_data(ttl=1800, show_spinner=False)
def _player_career(pid, pos) -> pd.DataFrame:
    from lib.db import player_career
    df = player_career(str(pid))
    if df.empty:
        return df
    df["pts_per_82"] = df["points"] / df["gp"] * 82
    df["season_year"] = df["season"].astype(str).str[:4].astype(int)
    df["season_label"] = df["season_year"].astype(str) + "-" + (df["season_year"]+1).astype(str).str[2:]
    return df

@st.cache_data(ttl=600, show_spinner=False)
def _goalie_games(pid) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT game_date AS date,
               shots_against AS SA, saves AS SV,
               ROUND(save_pct*100,2) AS "Sv%",
               goals_against AS GA,
               ROUND(toi_seconds/60.0,0) AS TOI
        FROM goalie_rolling_stats
        WHERE player_id={pid}
          AND season=(SELECT MAX(season) FROM games WHERE game_type='2')
        ORDER BY game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=600, show_spinner=False)
def _team_games(abbr) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT game_date AS date,
               opponent_abbr AS opp,
               CASE WHEN is_home THEN 'vs' ELSE '@' END AS ha,
               TRY_CAST(goals_for AS INTEGER) AS GF,
               TRY_CAST(goals_against AS INTEGER) AS GA,
               CASE WHEN TRY_CAST(team_points AS INTEGER)=2 THEN 'W'
                    WHEN TRY_CAST(team_points AS INTEGER)=1 THEN 'OTL'
                    ELSE 'L' END AS result
        FROM team_game_stats
        WHERE team_abbr='{abbr}' AND game_type='2'
          AND season=(SELECT MAX(season) FROM games WHERE game_type='2')
        ORDER BY game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=900, show_spinner=False)
def _ai_insight(name: str, team: str) -> str:
    df = query_fresh(f"""
        SELECT headline FROM agent_insights
        WHERE team_abbr='{team}' OR entity_name ILIKE '%{name.split()[0]}%'
        ORDER BY generated_at DESC LIMIT 1
    """)
    return str(df.iloc[0]["headline"]) if not df.empty else ""

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
CHART_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8896a8", size=10),
    margin=dict(l=0, r=0, t=20, b=0),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9)),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9)),
    hoverlabel=dict(bgcolor="#111", font_color="#f1f5f9"),
)

def _z_color(z) -> str:
    if pd.isna(z): return "#8896a8"
    z = float(z)
    if z >= 1.5:  return "#f97316"
    if z >= 0.5:  return "#5a8f4e"
    if z <= -1.5: return "#3b82f6"
    if z <= -0.5: return "#87ceeb"
    return "#8896a8"

def _z_str(z) -> str:
    if pd.isna(z): return "—"
    return f"+{float(z):.2f}σ" if float(z) >= 0 else f"{float(z):.2f}σ"

def _stat_block(label, value, color="#fff", size=20) -> str:
    return (
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:4px;padding:6px 10px;text-align:center;">'
        f'<div style="color:#8896a8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>'
        f'<div style="color:{color};font-weight:700;font-size:{size}px;font-family:monospace;'
        f'letter-spacing:-0.02em;">{value}</div>'
        f'</div>'
    )

def _panel_header(txt):
    st.markdown(
        f"<p style='color:#8896a8;font-size:9px;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.1em;margin:12px 0 6px;border-top:1px solid rgba(255,255,255,0.06);"
        f"padding-top:10px;'>{txt}</p>",
        unsafe_allow_html=True,
    )

def _headshot_html(url, name, z_color, size=64) -> str:
    if url:
        return (
            f'<img src="{url}" style="width:{size}px;height:{size}px;border-radius:50%;'
            f'object-fit:cover;border:2px solid {z_color}44;" '
            f'onerror="this.style.display=\'none\'">'
        )
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#5a8f4e;'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-weight:900;font-size:{size//3}px;color:#fff;flex-shrink:0;">'
        f'{name[0]}</div>'
    )

# ══════════════════════════════════════════════════════════════════════════════
#  TOP BAR  — mode selector + tab selector
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    f"<p style='color:#8896a8;font-size:9px;font-family:monospace;"
    f"margin:0 0 4px;'>THA ANALYTICS · TERMINAL · {get_data_date()}</p>",
    unsafe_allow_html=True,
)

bar_left, bar_mid, bar_right = st.columns([2, 3, 3])

with bar_left:
    mc = st.columns(3)
    for i, m in enumerate(["Skaters", "Goalies", "Teams"]):
        with mc[i]:
            active = st.session_state.t_mode == m
            if st.button(m, key=f"mode_{m}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.t_mode  = m
                st.session_state.t_id    = None
                st.session_state.t_filter= "All"
                st.session_state.t_tab   = "Overview"
                st.rerun()

with bar_mid:
    TABS = ["Overview", "Form", "Career", "Splits"]
    tc = st.columns(len(TABS))
    for i, t in enumerate(TABS):
        with tc[i]:
            active = st.session_state.t_tab == t
            if st.button(t, key=f"tab_{t}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.t_tab = t
                st.rerun()

with bar_right:
    st.session_state.t_search = st.text_input(
        "", placeholder="Search…",
        label_visibility="collapsed",
        value=st.session_state.t_search,
        key="t_search_input",
    )

st.markdown("<div style='height:4px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:8px;'></div>",
            unsafe_allow_html=True)

mode   = st.session_state.t_mode
tab    = st.session_state.t_tab
search = st.session_state.t_search

# ── Filter chips (context-aware) ───────────────────────────────────────────────
if mode == "Skaters":
    filters = ["All","ATL","MET","CEN","PAC","Fwd","Def","Hot","Cold"]
elif mode == "Goalies":
    filters = ["All","ATL","MET","CEN","PAC"]
else:
    filters = ["All","East","West","ATL","MET","CEN","PAC"]

chip_cols = st.columns(len(filters) + 6)
for i, f in enumerate(filters):
    with chip_cols[i]:
        active = st.session_state.t_filter == f
        if st.button(f, key=f"chip_{mode}_{f}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.t_filter = f
            st.rerun()

st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

# ── Build filtered list ────────────────────────────────────────────────────────
flt = st.session_state.t_filter

if mode == "Skaters":
    df_src = _skater_list()
    # Division filter
    if flt in DIV_TEAMS:
        df_src = df_src[df_src["team"].isin(DIV_TEAMS[flt])]
    elif flt == "Fwd":
        df_src = df_src[df_src["pos"].isin(["C","L","R"])]
    elif flt == "Def":
        df_src = df_src[df_src["pos"] == "D"]
    elif flt == "Hot":
        df_src = df_src[df_src["z"] >= 0.8]
    elif flt == "Cold":
        df_src = df_src[df_src["z"] <= -0.8]

elif mode == "Goalies":
    df_src = _goalie_list()
    if flt in DIV_TEAMS:
        df_src = df_src[df_src["team"].isin(DIV_TEAMS[flt])]

else:  # Teams
    df_src = _team_list()
    if flt == "East":
        df_src = df_src[df_src["conf"] == "E"]
    elif flt == "West":
        df_src = df_src[df_src["conf"] == "W"]
    elif flt in DIV_TEAMS:
        df_src = df_src[df_src["div"] == {"ATL":"A","MET":"M","CEN":"C","PAC":"P"}[flt]]

# Search
if search and len(search) >= 1:
    q = search.lower()
    if mode == "Teams":
        df_src = df_src[df_src["abbr"].str.lower().str.contains(q, na=False)]
    else:
        df_src = df_src[
            df_src["name"].str.lower().str.contains(q, na=False) |
            df_src["team"].str.lower().str.contains(q, na=False)
        ]

df_src = df_src.reset_index(drop=True)

# Auto-select top entity if none selected (or if mode changed)
if st.session_state.t_id is None and not df_src.empty:
    if mode == "Teams":
        st.session_state.t_id = df_src.iloc[0]["abbr"]
    else:
        st.session_state.t_id = df_src.iloc[0]["pid"]

# ══════════════════════════════════════════════════════════════════════════════
#  3-PANEL LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
col_left, col_center, col_right = st.columns([1.5, 3.4, 1.8], gap="small")

# ─────────────────────────────────────────────────────────────────────────────
#  LEFT PANEL — scrollable clickable list
# ─────────────────────────────────────────────────────────────────────────────
with col_left:
    st.markdown(
        f"<p style='color:#8896a8;font-size:9px;margin:0 0 4px;font-family:monospace;'>"
        f"{len(df_src)} {mode.lower()}</p>",
        unsafe_allow_html=True,
    )

    # Build display df
    if mode == "Skaters":
        df_disp = df_src[["name","team","pos","pts","z"]].copy()
        df_disp.columns = ["Player","Tm","P","PTS","Form σ"]
    elif mode == "Goalies":
        df_disp = df_src[["name","team","gp","sv_pct","z"]].copy()
        df_disp.columns = ["Goalie","Tm","GP","Sv%","Form σ"]
    else:
        df_disp = df_src[["abbr","div","pts","pp_pct","z"]].copy()
        df_disp.columns = ["Team","Div","PTS","PP%","Form σ"]

    # Style σ column
    def _style_sigma(val):
        if pd.isna(val): return "color:#8896a8"
        v = float(val)
        if v >= 1.5:  return "color:#f97316;font-weight:bold"
        if v >= 0.5:  return "color:#5a8f4e;font-weight:bold"
        if v <= -1.5: return "color:#3b82f6"
        if v <= -0.5: return "color:#87ceeb"
        return "color:#8896a8"

    styled = df_disp.style.applymap(_style_sigma, subset=["Form σ"])

    event = st.dataframe(
        styled,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        height=580,
        hide_index=True,
    )

    # Update selected id from click
    if event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        if idx < len(df_src):
            new_id = df_src.iloc[idx]["abbr" if mode == "Teams" else "pid"]
            if st.session_state.t_id != new_id:
                st.session_state.t_id = new_id
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  CENTER PANEL — tab-based contextual view
# ─────────────────────────────────────────────────────────────────────────────
with col_center:
    sel_id = st.session_state.t_id
    if sel_id is None:
        st.markdown(
            "<p style='color:#8896a8;margin-top:60px;text-align:center;'>"
            "Select an entity from the list</p>",
            unsafe_allow_html=True,
        )
    else:
        # ── SKATER CENTER ──────────────────────────────────────────────────────
        if mode == "Skaters":
            row = df_src[df_src["pid"] == sel_id]
            if row.empty:
                st.info("Player not found in current filter.")
            else:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))

                # ── Bio strip ──────────────────────────────────────────────────
                if bio is not None:
                    h_cm = int(bio["heightInCentimeters"]) if bio["heightInCentimeters"] else 0
                    w_kg = int(bio["weightInKilograms"])   if bio["weightInKilograms"]   else 0
                    feet, inch = divmod(round(h_cm/2.54), 12)
                    lbs  = round(w_kg*2.205)
                    birth = str(bio["birthDate"])[:10] if bio["birthDate"] else "—"
                    num   = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    hs    = str(bio["headshot"]) if bio["headshot"] else ""
                    img   = _headshot_html(hs, row["name"], zc, 52)
                    st.html(f"""
                    <div style="display:flex;align-items:center;gap:14px;
                                border-bottom:1px solid rgba(255,255,255,0.08);
                                padding-bottom:10px;margin-bottom:10px;">
                      {img}
                      <div style="flex:1;">
                        <div style="color:#fff;font-weight:800;font-size:17px;
                                    letter-spacing:-0.02em;">{row['name']}</div>
                        <div style="color:#8896a8;font-size:11px;margin-top:1px;">
                          #{num} · {row['pos']} · {row['team']} ·
                          {feet}'{inch}" · {lbs} lbs · {birth[:4] if birth != '—' else '—'}
                        </div>
                      </div>
                      <div style="text-align:right;">
                        <div style="color:{zc};font-weight:900;font-size:24px;
                                    font-family:monospace;">{_z_str(row['z'])}</div>
                        <div style="color:#8896a8;font-size:9px;">5g vs 20g baseline</div>
                      </div>
                    </div>
                    """)

                # ── OVERVIEW TAB ───────────────────────────────────────────────
                if tab == "Overview":
                    pm   = row["pm"]
                    pm_s = (f"+{int(pm)}" if pm > 0 else str(int(pm))) if pd.notna(pm) else "—"
                    pm_c = "#5a8f4e" if (pd.notna(pm) and pm > 0) else ("#c41e3a" if (pd.notna(pm) and pm < 0) else "#8896a8")
                    ppp  = int(row["ppp"])  if pd.notna(row["ppp"])   else "—"
                    sh   = f'{row["sh_pct"]:.1f}%' if pd.notna(row["sh_pct"]) else "—"
                    fo   = f'{row["fo_pct"]:.1f}%' if (pd.notna(row["fo_pct"]) and float(row["fo_pct"]) > 0) else "—"
                    toi  = f'{row["toi"]:.1f}' if pd.notna(row["toi"]) else "—"

                    cols_stats = st.columns(7)
                    stats = [
                        ("GP", int(row["gp"]),       "#fff"),
                        ("G",  int(row["g"]),         "#fff"),
                        ("A",  int(row["a"]),         "#8896a8"),
                        ("PTS",int(row["pts"]),       "#5a8f4e"),
                        ("+/-",pm_s,                  pm_c),
                        ("PPP",ppp,                   "#87ceeb"),
                        ("TOI",toi,                   "#8896a8"),
                    ]
                    for i,(lbl,val,col) in enumerate(stats):
                        with cols_stats[i]:
                            st.html(_stat_block(lbl, val, col))

                    c2 = st.columns(4)
                    s2 = [
                        ("SH%",      sh,                              "#8896a8"),
                        ("FO%",      fo,                              "#8896a8"),
                        ("5g avg",   f"{row['avg5']:.2f}",            "#f97316"),
                        ("20g avg",  f"{float(row['avg5']):.2f}" if True else "—", "#8896a8"),
                    ]
                    s2[3] = ("20g avg", f"{float(df_src[df_src['pid']==sel_id]['z'].iloc[0]):.2f}σ", _z_color(row['z']))
                    for i,(lbl,val,col) in enumerate(s2):
                        with c2[i]:
                            st.html(_stat_block(lbl, val, col))

                    _panel_header("Last 12 games — current season")
                    df_games = _player_games(int(sel_id))
                    if not df_games.empty:
                        rows_html = ""
                        for _, g in df_games.iterrows():
                            pts_c = "#f97316" if g["PTS"] >= 2 else ("#5a8f4e" if g["PTS"] == 1 else "#8896a8")
                            rows_html += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;font-family:monospace;">{str(g["date"])[:10]}</td>'
                                f'<td style="padding:4px 8px;color:#fff;font-size:11px;text-align:center;">{int(g["G"])}</td>'
                                f'<td style="padding:4px 8px;color:#8896a8;font-size:11px;text-align:center;">{int(g["A"])}</td>'
                                f'<td style="padding:4px 8px;color:{pts_c};font-weight:700;font-size:11px;text-align:center;">{int(g["PTS"])}</td>'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;font-family:monospace;text-align:right;">{g["TOI"]}</td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Date</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;text-align:center;">G</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;text-align:center;">A</th>'
                            f'<th style="padding:4px 8px;color:#5a8f4e;font-size:9px;text-align:center;">PTS</th>'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:right;">TOI</th>'
                            f'</tr></thead><tbody>{rows_html}</tbody></table>'
                        )

                # ── FORM TAB ───────────────────────────────────────────────────
                elif tab == "Form":
                    df_form = _player_form_series(int(sel_id))
                    if not df_form.empty:
                        df_form = df_form.copy()
                        df_form["roll5"] = df_form["pts"].rolling(5, min_periods=2).mean()
                        season_avg = df_form["pts"].mean()

                        fig = go.Figure()
                        fig.add_bar(
                            x=df_form["date"].astype(str).str[:10],
                            y=df_form["pts"],
                            marker_color=[_z_color(1.6) if p >= 2 else (_z_color(0.6) if p == 1 else "rgba(255,255,255,0.12)") for p in df_form["pts"]],
                            name="Points",
                            hovertemplate="%{x}: %{y} pts<extra></extra>",
                        )
                        fig.add_scatter(
                            x=df_form["date"].astype(str).str[:10],
                            y=df_form["roll5"],
                            mode="lines",
                            line=dict(color="#f97316", width=2),
                            name="5g avg",
                            hovertemplate="%{x}: %{y:.2f} 5g avg<extra></extra>",
                        )
                        fig.add_hline(y=season_avg, line_dash="dot",
                                      line_color="rgba(255,255,255,0.2)",
                                      annotation_text=f"Season avg {season_avg:.2f}",
                                      annotation_font_size=9,
                                      annotation_font_color="rgba(255,255,255,0.4)")
                        layout = dict(**CHART_BASE)
                        layout["height"] = 280
                        layout["legend"] = dict(orientation="h", y=1.05, font=dict(size=9))
                        layout["title"] = dict(text=f"Points per game — {row['name']}", font=dict(size=11, color="#8896a8"), x=0)
                        fig.update_layout(**layout)
                        fig.update_xaxes(tickangle=45, nticks=12)
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                        # Z-score context
                        zval = float(row["z"]) if pd.notna(row["z"]) else 0
                        zc   = _z_color(zval)
                        last5 = df_form["pts"].tail(5).sum()
                        last20 = df_form["pts"].tail(20).mean() if len(df_form) >= 10 else season_avg
                        st.html(f"""
                        <div style="display:flex;gap:12px;margin-top:8px;flex-wrap:wrap;">
                          <div style="background:rgba(255,255,255,0.03);border:1px solid {zc}33;
                                      border-radius:4px;padding:8px 14px;flex:1;">
                            <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Form (σ)</div>
                            <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;">{_z_str(row['z'])}</div>
                            <div style="color:#8896a8;font-size:9px;">5g vs 20g baseline</div>
                          </div>
                          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                      border-radius:4px;padding:8px 14px;flex:1;">
                            <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Last 5 games</div>
                            <div style="color:#f97316;font-weight:900;font-size:22px;">{last5} pts</div>
                            <div style="color:#8896a8;font-size:9px;">{float(row['avg5']):.2f} avg/g</div>
                          </div>
                          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                      border-radius:4px;padding:8px 14px;flex:1;">
                            <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Season avg</div>
                            <div style="color:#fff;font-weight:900;font-size:22px;">{season_avg:.2f}</div>
                            <div style="color:#8896a8;font-size:9px;">pts per game</div>
                          </div>
                        </div>
                        """)

                # ── CAREER TAB ─────────────────────────────────────────────────
                elif tab == "Career":
                    df_car = _player_career(int(sel_id), row["pos"])
                    if not df_car.empty:
                        fig_arc = go.Figure()
                        fig_arc.add_scatter(
                            x=df_car["season_label"],
                            y=df_car["pts_per_82"],
                            mode="lines+markers",
                            line=dict(color="#5a8f4e", width=2),
                            marker=dict(size=5),
                            fill="tozeroy",
                            fillcolor="rgba(90,143,78,0.07)",
                            name="PTS/82",
                            hovertemplate="%{x}: %{y:.0f} PTS/82<extra></extra>",
                        )
                        layout_arc = dict(**CHART_BASE)
                        layout_arc["height"] = 180
                        layout_arc["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(size=9), title="PTS/82")
                        fig_arc.update_layout(**layout_arc)
                        fig_arc.update_xaxes(type="category", tickangle=45, nticks=10)
                        st.plotly_chart(fig_arc, use_container_width=True, config={"displayModeBar": False})

                        rows = ""
                        for _, r in df_car.sort_values("season_year", ascending=False).iterrows():
                            p82_c = "#f97316" if r["pts_per_82"] >= 80 else ("#5a8f4e" if r["pts_per_82"] >= 50 else "#8896a8")
                            gp_c  = "#5a8f4e" if r["gp"] >= 70 else ("#f97316" if r["gp"] >= 50 else "#c41e3a")
                            rows += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:4px 10px;color:#fff;font-weight:600;font-size:11px;">{r["season_label"]}</td>'
                                f'<td style="padding:4px 6px;color:{gp_c};font-size:11px;text-align:right;">{int(r["gp"])}</td>'
                                f'<td style="padding:4px 6px;color:#fff;font-size:11px;text-align:right;">{int(r["goals"])}</td>'
                                f'<td style="padding:4px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(r["assists"])}</td>'
                                f'<td style="padding:4px 6px;color:#5a8f4e;font-weight:700;font-size:11px;text-align:right;">{int(r["points"])}</td>'
                                f'<td style="padding:4px 10px;color:{p82_c};font-family:monospace;font-size:11px;text-align:right;">{r["pts_per_82"]:.0f}</td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Season</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">GP</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">G</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">A</th>'
                            f'<th style="padding:4px 6px;color:#5a8f4e;font-size:9px;text-align:right;">PTS</th>'
                            f'<th style="padding:4px 10px;color:#f97316;font-size:9px;text-align:right;">PTS/82</th>'
                            f'</tr></thead><tbody>{rows}</tbody></table>'
                        )

                # ── SPLITS TAB ─────────────────────────────────────────────────
                elif tab == "Splits":
                    st.markdown(
                        "<p style='color:#8896a8;font-size:11px;margin-top:16px;'>Home/Away and special teams "
                        "splits coming in next update. Use Career tab for season-by-season data.</p>",
                        unsafe_allow_html=True,
                    )
                    st.page_link("pages/8_Player_History.py", label="→ Full Player History page",
                                 icon=":material/show_chart:")

        # ── GOALIE CENTER ──────────────────────────────────────────────────────
        elif mode == "Goalies":
            row = df_src[df_src["pid"] == sel_id]
            if row.empty:
                st.info("Goalie not found in current filter.")
            else:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))

                if bio is not None:
                    hs  = str(bio["headshot"]) if bio["headshot"] else ""
                    num = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    img = _headshot_html(hs, row["name"], zc, 52)
                    st.html(f"""
                    <div style="display:flex;align-items:center;gap:14px;
                                border-bottom:1px solid rgba(255,255,255,0.08);
                                padding-bottom:10px;margin-bottom:10px;">
                      {img}
                      <div style="flex:1;">
                        <div style="color:#fff;font-weight:800;font-size:17px;">{row['name']}</div>
                        <div style="color:#8896a8;font-size:11px;">#{num} · G · {row['team']}</div>
                      </div>
                      <div style="text-align:right;">
                        <div style="color:{zc};font-weight:900;font-size:24px;font-family:monospace;">{_z_str(row['z'])}</div>
                        <div style="color:#8896a8;font-size:9px;">Sv% form</div>
                      </div>
                    </div>
                    """)

                if tab == "Overview":
                    sv  = float(row["sv_pct"]) if pd.notna(row["sv_pct"]) else 0
                    sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else "#8896a8")
                    gaa  = float(row["gaa"])  if pd.notna(row["gaa"])  else 0
                    gaa_c = "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")

                    gc = st.columns(6)
                    gstats = [
                        ("GP",   int(row["gp"]),            "#fff"),
                        ("W",    int(row["w"]) if pd.notna(row["w"]) else "—", "#5a8f4e"),
                        ("Sv%",  f"{sv:.2f}%",              sv_c),
                        ("GAA",  f"{gaa:.2f}",              gaa_c),
                        ("SO",   int(row["so"]) if pd.notna(row["so"]) else 0, "#8896a8"),
                        ("Sv%/5g", f"{float(row['sv5']):.2f}%", "#f97316"),
                    ]
                    for i,(lbl,val,col) in enumerate(gstats):
                        with gc[i]:
                            st.html(_stat_block(lbl, val, col))

                    _panel_header("Last 12 games")
                    df_gg = _goalie_games(int(sel_id))
                    if not df_gg.empty:
                        rows_html = ""
                        for _, g in df_gg.iterrows():
                            sv_val = float(g['Sv%'])
                            sv_col = "#f97316" if sv_val >= 93 else ("#5a8f4e" if sv_val >= 91 else ("#8896a8" if sv_val >= 89 else "#87ceeb"))
                            rows_html += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;font-family:monospace;">{str(g["date"])[:10]}</td>'
                                f'<td style="padding:4px 8px;color:#8896a8;font-size:10px;text-align:center;">{int(g["SA"])}</td>'
                                f'<td style="padding:4px 8px;color:#fff;font-size:10px;text-align:center;">{int(g["SV"])}</td>'
                                f'<td style="padding:4px 8px;color:{sv_col};font-family:monospace;font-size:11px;text-align:center;">{sv_val:.2f}%</td>'
                                f'<td style="padding:4px 8px;color:#c41e3a;font-size:10px;text-align:center;">{int(g["GA"])}</td>'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;text-align:right;">{int(g["TOI"])}</td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Date</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;text-align:center;">SA</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;text-align:center;">SV</th>'
                            f'<th style="padding:4px 8px;color:#f97316;font-size:9px;text-align:center;">Sv%</th>'
                            f'<th style="padding:4px 8px;color:#c41e3a;font-size:9px;text-align:center;">GA</th>'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:right;">TOI</th>'
                            f'</tr></thead><tbody>{rows_html}</tbody></table>'
                        )

                elif tab == "Career":
                    st.page_link("pages/11_Goalies.py", label="→ Full Goalie profile with career arc",
                                 icon=":material/sports:")

        # ── TEAM CENTER ────────────────────────────────────────────────────────
        else:
            row = df_src[df_src["abbr"] == sel_id]
            if row.empty:
                st.info("Team not in current filter.")
            else:
                row  = row.iloc[0]
                zc   = _z_color(row["z"])
                diff = int(row["diff"]) if pd.notna(row["diff"]) else 0
                diff_c = "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")
                _div_map  = {'A':'Atlantic','M':'Metropolitan','C':'Central','P':'Pacific'}
                _conf_map = {'E':'Eastern','W':'Western'}
                t_div_label  = _div_map.get(row['div'],  row['div'])
                t_conf_label = _conf_map.get(row['conf'], row['conf'])

                st.html(f"""
                <div style="display:flex;align-items:center;gap:16px;
                            border-bottom:1px solid rgba(255,255,255,0.08);
                            padding-bottom:10px;margin-bottom:10px;">
                  <div style="font-weight:900;font-size:36px;color:#fff;
                              font-family:monospace;letter-spacing:-0.02em;">{row['abbr']}</div>
                  <div style="flex:1;">
                    <div style="color:#8896a8;font-size:11px;">
                      {t_div_label} Division ·
                      {t_conf_label} Conference
                    </div>
                  </div>
                  <div style="text-align:right;">
                    <div style="color:{zc};font-weight:900;font-size:24px;font-family:monospace;">{_z_str(row['z'])}</div>
                    <div style="color:#8896a8;font-size:9px;">form σ</div>
                  </div>
                </div>
                """)

                if tab == "Overview":
                    pp  = float(row["pp_pct"]) if pd.notna(row["pp_pct"]) else 0
                    pk  = float(row["pk_pct"]) if pd.notna(row["pk_pct"]) else 0
                    tc_ = st.columns(8)
                    tstats = [
                        ("GP",   int(row["gp"]),   "#8896a8"),
                        ("W",    int(row["w"]),     "#5a8f4e"),
                        ("L",    int(row["l"]),     "#c41e3a"),
                        ("OTL",  int(row["otl"]),   "#8896a8"),
                        ("PTS",  int(row["pts"]),   "#5a8f4e"),
                        ("DIFF", (f"+{diff}" if diff>0 else str(diff)), diff_c),
                        ("PP%",  f"{pp:.1f}%",      "#f97316" if pp >= 25 else "#8896a8"),
                        ("PK%",  f"{pk:.1f}%",      "#87ceeb" if pk >= 83 else "#8896a8"),
                    ]
                    for i,(lbl,val,col) in enumerate(tstats):
                        with tc_[i]:
                            st.html(_stat_block(lbl, val, col))

                    _panel_header("Last 12 games")
                    df_tg = _team_games(sel_id)
                    if not df_tg.empty:
                        rows_html = ""
                        for _, g in df_tg.iterrows():
                            res = str(g["result"])
                            res_c = "#5a8f4e" if res=="W" else ("#87ceeb" if res=="OTL" else "#c41e3a")
                            score_c = "#5a8f4e" if (pd.notna(g["GF"]) and pd.notna(g["GA"]) and g["GF"]>g["GA"]) else "#c41e3a"
                            score = f'{int(g["GF"])}–{int(g["GA"])}' if pd.notna(g["GF"]) else "—"
                            rows_html += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;font-family:monospace;">{str(g["date"])[:10]}</td>'
                                f'<td style="padding:4px 8px;color:#8896a8;font-size:10px;">{g["ha"]}</td>'
                                f'<td style="padding:4px 8px;color:#fff;font-weight:600;font-size:11px;font-family:monospace;">{g["opp"]}</td>'
                                f'<td style="padding:4px 8px;color:{score_c};font-family:monospace;font-size:11px;text-align:center;">{score}</td>'
                                f'<td style="padding:4px 10px;text-align:center;">'
                                f'<span style="color:{res_c};background:{res_c}22;padding:1px 6px;'
                                f'border-radius:3px;font-size:10px;font-weight:700;">{res}</span></td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Date</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;">H/A</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;">Opp</th>'
                            f'<th style="padding:4px 8px;color:#8896a8;font-size:9px;text-align:center;">Score</th>'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:center;">Result</th>'
                            f'</tr></thead><tbody>{rows_html}</tbody></table>'
                        )

                elif tab == "Career":
                    st.page_link("pages/9_Team_History.py", label="→ Full Team History with franchise arc",
                                 icon=":material/history:")

# ─────────────────────────────────────────────────────────────────────────────
#  RIGHT PANEL — quick stats card (always visible)
# ─────────────────────────────────────────────────────────────────────────────
with col_right:
    sel_id = st.session_state.t_id
    if sel_id is None:
        st.markdown(
            "<p style='color:rgba(255,255,255,0.2);font-size:11px;margin-top:40px;text-align:center;'>—</p>",
            unsafe_allow_html=True,
        )
    else:
        # ── Skater right card ──────────────────────────────────────────────────
        if mode == "Skaters":
            row = df_src[df_src["pid"] == sel_id]
            if not row.empty:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))
                hs  = str(bio["headshot"]) if (bio is not None and bio["headshot"]) else ""
                img = _headshot_html(hs, row["name"], zc, 56)
                pm  = row["pm"]
                pm_s = (f"+{int(pm)}" if pm > 0 else str(int(pm))) if pd.notna(pm) else "—"
                pm_c = "#5a8f4e" if (pd.notna(pm) and pm > 0) else ("#c41e3a" if (pd.notna(pm) and pm < 0) else "#8896a8")
                ppp  = int(row["ppp"]) if pd.notna(row["ppp"]) else "—"
                insight = _ai_insight(row["name"], row["team"])

                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    {img}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:12px;line-height:1.3;">{row['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">{row['pos']} · {row['team']}</div>
                    </div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;
                              text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);
                              padding-bottom:8px;margin-bottom:8px;">{_z_str(row['z'])}</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px;">
                    {_stat_block('PTS', int(row['pts']), '#5a8f4e', 16)}
                    {_stat_block('+/-', pm_s, pm_c, 16)}
                    {_stat_block('G', int(row['g']), '#fff', 16)}
                    {_stat_block('A', int(row['a']), '#8896a8', 16)}
                    {_stat_block('PPP', ppp, '#87ceeb', 16)}
                    {_stat_block('5g', f"{row['avg5']:.2f}", '#f97316', 16)}
                  </div>
                  {f'<div style="background:rgba(255,255,255,0.02);border-radius:4px;padding:7px 8px;margin-bottom:8px;"><div style="color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:3px;">AI Insight</div><div style="color:#8896a8;font-size:10px;line-height:1.5;">{insight}</div></div>' if insight else ''}
                  <div style="display:flex;gap:6px;flex-direction:column;">
                    <a href="/Player_History" target="_self"
                       style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                      Full career profile →</a>
                  </div>
                </div>
                """)

        # ── Goalie right card ──────────────────────────────────────────────────
        elif mode == "Goalies":
            row = df_src[df_src["pid"] == sel_id]
            if not row.empty:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))
                hs  = str(bio["headshot"]) if (bio is not None and bio["headshot"]) else ""
                img = _headshot_html(hs, row["name"], zc, 56)
                sv  = float(row["sv_pct"]) if pd.notna(row["sv_pct"]) else 0
                sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else "#8896a8")
                gaa  = float(row["gaa"])  if pd.notna(row["gaa"])  else 0
                gaa_c = "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")

                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    {img}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:12px;">{row['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">G · {row['team']}</div>
                    </div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;
                              text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);
                              padding-bottom:8px;margin-bottom:8px;">{_z_str(row['z'])}</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px;">
                    {_stat_block('Sv%', f'{sv:.2f}%', sv_c, 15)}
                    {_stat_block('GAA', f'{gaa:.2f}', gaa_c, 15)}
                    {_stat_block('W', int(row['w']) if pd.notna(row['w']) else '—', '#5a8f4e', 15)}
                    {_stat_block('GP', int(row['gp']), '#8896a8', 15)}
                    {_stat_block('Sv%/5g', f'{float(row["sv5"]):.2f}%', '#f97316', 14)}
                    {_stat_block('SO', int(row['so']) if pd.notna(row['so']) else 0, '#8896a8', 15)}
                  </div>
                  <a href="/Goalies" target="_self"
                     style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                    Full goalie profile →</a>
                </div>
                """)

        # ── Team right card ────────────────────────────────────────────────────
        else:
            row = df_src[df_src["abbr"] == sel_id]
            if not row.empty:
                row  = row.iloc[0]
                zc   = _z_color(row["z"])
                diff = int(row["diff"]) if pd.notna(row["diff"]) else 0
                diff_c = "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")
                pp   = float(row["pp_pct"]) if pd.notna(row["pp_pct"]) else 0
                pk   = float(row["pk_pct"]) if pd.notna(row["pk_pct"]) else 0
                insight = _ai_insight("", row["abbr"])
                _r_div_map = {'A':'Atlantic','M':'Metropolitan','C':'Central','P':'Pacific'}
                r_div_label = _r_div_map.get(row['div'], '—')

                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="margin-bottom:10px;">
                    <div style="color:#fff;font-weight:900;font-size:28px;font-family:monospace;">{row['abbr']}</div>
                    <div style="color:#8896a8;font-size:10px;">
                      {r_div_label} Division
                    </div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;
                              text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);
                              padding-bottom:8px;margin-bottom:8px;">{_z_str(row['z'])}</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px;">
                    {_stat_block('PTS', int(row['pts']), '#5a8f4e', 16)}
                    {_stat_block('W–L', f"{int(row['w'])}–{int(row['l'])}", '#fff', 14)}
                    {_stat_block('DIFF', (f"+{diff}" if diff>0 else str(diff)), diff_c, 16)}
                    {_stat_block('PP%', f'{pp:.1f}%', '#f97316' if pp>=25 else '#8896a8', 15)}
                    {_stat_block('PK%', f'{pk:.1f}%', '#87ceeb' if pk>=83 else '#8896a8', 15)}
                    {_stat_block('SF/g', f'{float(row["sf"]):.1f}' if pd.notna(row["sf"]) else '—', '#8896a8', 15)}
                  </div>
                  {f'<div style="background:rgba(255,255,255,0.02);border-radius:4px;padding:7px 8px;margin-bottom:8px;"><div style="color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:3px;">AI Insight</div><div style="color:#8896a8;font-size:10px;line-height:1.5;">{insight}</div></div>' if insight else ''}
                  <a href="/Teams" target="_self"
                     style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                    Team dashboard →</a>
                </div>
                """)

# ── Legend ─────────────────────────────────────────────────────────────────────
st.markdown(
    """<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;padding-top:10px;
                  border-top:1px solid rgba(255,255,255,0.06);">
      <span style="color:#f97316;font-size:9px;">■ Hot σ ≥ 1.5</span>
      <span style="color:#5a8f4e;font-size:9px;">■ Above avg σ ≥ 0.5</span>
      <span style="color:#8896a8;font-size:9px;">■ Neutral</span>
      <span style="color:#87ceeb;font-size:9px;">■ Below avg σ ≤ −0.5</span>
      <span style="color:#3b82f6;font-size:9px;">■ Cold σ ≤ −1.5</span>
      <span style="color:rgba(255,255,255,0.25);font-size:9px;margin-left:8px;">
        σ = z-score vs 20-game baseline · click any row to select</span>
    </div>""",
    unsafe_allow_html=True,
)
