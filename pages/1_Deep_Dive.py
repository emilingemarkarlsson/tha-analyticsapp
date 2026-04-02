"""Deep Dive – 3-panel hockey analytics terminal."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login

st.set_page_config(page_title="Deep Dive – THA Analytics", layout="wide", initial_sidebar_state="expanded")

# ── Session state helper ───────────────────────────────────────────────────────
def _ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


_render_sidebar()
require_login()

# ── Page header ─────────────────────────────────────────────────────────────────
# Injected before CSS so it sits at top
_header_date = get_data_date()

# ── Terminal CSS ────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="block-container"] {
    padding-top:0.4rem !important; padding-bottom:0 !important;
    padding-left:0.8rem !important; padding-right:0.8rem !important;
}
[data-testid="stHorizontalBlock"] { gap:6px !important; }
[data-testid="stDataFrame"] thead th {
    font-size:11px !important; text-transform:uppercase; letter-spacing:0.05em;
    background:rgba(255,255,255,0.04) !important; padding:5px 8px !important;
    color:#8896a8 !important;
}
[data-testid="stDataFrame"] tbody td {
    font-size:13px !important; padding:4px 8px !important;
    font-family:'SF Mono','Fira Code',monospace !important;
}
[data-testid="stDataFrame"] tbody tr { height:28px !important; }
[data-testid="stDataFrame"] tbody tr:hover td { background:rgba(90,143,78,0.10) !important; }
[data-testid="stDataFrame"] [aria-selected="true"] td { background:rgba(90,143,78,0.18) !important; border-left:2px solid #5a8f4e !important; }
details summary { padding:3px 0 !important; font-size:10px !important; }
/* Compact top-bar and filter buttons */
div[data-testid="stButton"] > button {
    padding:3px 10px !important;
    font-size:11px !important;
    line-height:1.5 !important;
    min-height:32px !important;
}
/* Search input: no top label gap */
div[data-testid="stTextInput"] { margin-top:0 !important; }
div[data-testid="stTextInput"] > label { display:none !important; }
div[data-testid="stTextInput"] input {
    font-size:11px !important;
    padding:6px 10px !important;
    min-height:32px !important;
}
</style>""", unsafe_allow_html=True)

from lib.components import page_header as _page_header
from lib.entitlements import gate, soft_gate, has_feature, watchlist_slots_remaining
_page_header("Deep Dive", "Players · Teams · Compare — click any row for full stats", data_date=_header_date)

# ── Session state ───────────────────────────────────────────────────────────────
_ss("t_mode",     "Players")   # Players | Teams | Compare
_ss("t_sub",      "Skaters")   # Skaters | Goalies  (when mode=Players)
_ss("t_tab",      "Overview")  # Overview | Career | Splits
_ss("t_filter",      "All")
_ss("t_filter_geo",  "All")    # Conf/Division dropdown
_ss("t_filter_type", "All")    # Player-type dropdown (skaters only)
_ss("t_chart_range", "Season") # Chart time-window toggle
_ss("t_id",       None)
_ss("t_search",   "")
_ss("t_sort",     "z")         # sort column for left list
_ss("t_cmp_a",    None)
_ss("t_cmp_b",    None)
_ss("t_cmp_type", "Skaters")   # Skaters | Teams

DIV_TEAMS = {
    "ATL": ["TBL","BUF","MTL","BOS","OTT","DET","TOR","FLA"],
    "MET": ["CAR","NYI","CBJ","PIT","PHI","WSH","NJD","NYR"],
    "CEN": ["COL","DAL","MIN","UTA","NSH","WPG","STL","CHI"],
    "PAC": ["ANA","EDM","VGK","LAK","SEA","SJS","CGY","VAN"],
}
EAST = DIV_TEAMS["ATL"] + DIV_TEAMS["MET"]
WEST = DIV_TEAMS["CEN"] + DIV_TEAMS["PAC"]

# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def _season_pfx() -> str:
    """Returns game_id LIKE prefix for current regular season, e.g. '202502%'."""
    df = query("SELECT MAX(season) FROM standings")
    season = int(df.iloc[0, 0])   # e.g. 20252026
    year   = season // 10000       # 2025
    return f"{year}02%"            # '202502%'
@st.cache_data(ttl=900, show_spinner=False)
def _skater_list() -> pd.DataFrame:
    return query("""
        SELECT CAST(pr.player_id AS VARCHAR) AS pid,
               pr.player_first_name || ' ' || pr.player_last_name AS name,
               pr.team_abbr AS team, pr.position AS pos,
               pr.gp_season AS gp,
               CAST(pr.goals_season AS INTEGER)   AS g,
               CAST(pr.assists_season AS INTEGER)  AS a,
               CAST(pr.pts_season AS INTEGER)      AS pts,
               ROUND(pr.pts_avg_5g, 2)             AS avg5,
               ROUND(pr.pts_zscore_5v20, 2)        AS z,
               ss.plusMinus AS pm,
               ss.ppPoints  AS ppp,
               ROUND(ss.shootingPct*100,1)         AS sh_pct,
               ROUND(ss.faceoffWinPct*100,1)       AS fo_pct,
               ROUND(pr.toi_avg_10g/60.0, 1)       AS toi
        FROM player_rolling_stats pr
        LEFT JOIN skater_stats ss ON ss.playerId=pr.player_id AND ss.season=pr.season
        WHERE pr.game_recency_rank=1
          AND pr.season=(SELECT MAX(season) FROM games WHERE game_type='2')
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
               ROUND(gs.savePct*100, 2)          AS sv_pct,
               ROUND(gs.goalsAgainstAverage, 2)  AS gaa,
               gs.shutouts AS so,
               ROUND(gr.sv_pct_avg_5g*100, 2)    AS sv5,
               ROUND(gr.sv_pct_zscore_5v20, 2)   AS z
        FROM goalie_rolling_stats gr
        LEFT JOIN goalie_stats gs ON gs.playerId=gr.player_id AND gs.season=gr.season
        WHERE gr.game_recency_rank=1
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
               ROUND(ts.powerPlayPct*100,1)      AS pp_pct,
               ROUND(ts.penaltyKillPct*100,1)    AS pk_pct,
               ROUND(ts.shotsForPerGame,1)        AS sf,
               ROUND(tr.pts_zscore_5v20, 2)       AS z,
               ROUND(tr.gf_avg_10g, 2)            AS gf10,
               ROUND(tr.ga_avg_10g, 2)            AS ga10
        FROM standings st
        LEFT JOIN team_stats ts    ON ts.teamFullName=st.teamName AND ts.season=st.season
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
    pfx = _season_pfx()
    return query_fresh(f"""
        SELECT pgs.game_date AS date,
               opp.team_abbr AS opp,
               CASE WHEN pgs.is_home THEN 'vs' ELSE '@' END AS ha,
               pgs.goals AS G, pgs.assists AS A, pgs.points AS PTS,
               ROUND(pgs.toi_seconds/60.0,1) AS TOI
        FROM player_game_stats pgs
        LEFT JOIN (SELECT game_id, team_abbr FROM team_game_stats
                   WHERE CAST(game_id AS VARCHAR) LIKE '{pfx}') opp
               ON opp.game_id=pgs.game_id AND opp.team_abbr != pgs.team_abbr
        WHERE pgs.player_id={pid}
          AND CAST(pgs.game_id AS VARCHAR) LIKE '{pfx}'
        ORDER BY pgs.game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=600, show_spinner=False)
def _player_form_series(pid) -> pd.DataFrame:
    pfx = _season_pfx()
    return query_fresh(f"""
        SELECT game_date AS date, points AS pts
        FROM player_game_stats
        WHERE player_id={pid}
          AND CAST(game_id AS VARCHAR) LIKE '{pfx}'
        ORDER BY game_date
    """)

@st.cache_data(ttl=1800, show_spinner=False)
def _player_career(pid) -> pd.DataFrame:
    from lib.db import player_career
    df = player_career(str(pid))
    if df.empty: return df
    df["pts_per_82"] = (df["points"] / df["gp"] * 82).round(1)
    df["season_year"]  = df["season"].astype(str).str[:4].astype(int)
    df["season_label"] = df["season_year"].astype(str) + "-" + (df["season_year"]+1).astype(str).str[2:]
    return df

@st.cache_data(ttl=600, show_spinner=False)
def _goalie_games(pid) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT game_date AS date, shots_against AS SA, saves AS SV,
               ROUND(save_pct*100,2) AS sv_pct,
               goals_against AS GA, ROUND(toi_seconds/60.0,0) AS TOI,
               is_home
        FROM goalie_rolling_stats
        WHERE player_id={pid}
          AND season=(SELECT MAX(season) FROM games WHERE game_type=2)
        ORDER BY game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=600, show_spinner=False)
def _team_games(abbr) -> pd.DataFrame:
    pfx = _season_pfx()
    return query_fresh(f"""
        SELECT a.game_date AS date,
               b.team_abbr AS opp,
               CASE WHEN a.is_home THEN 'vs' ELSE '@' END AS ha,
               CAST(a.gf AS INTEGER) AS GF,
               CAST(b.gf AS INTEGER) AS GA,
               CASE WHEN a.gf > b.gf THEN 'W'
                    WHEN a.gf < b.gf THEN 'L'
                    ELSE 'OTL' END AS result
        FROM (
            SELECT game_id, game_date, team_abbr, is_home, SUM(goals) AS gf
            FROM player_game_stats
            WHERE CAST(game_id AS VARCHAR) LIKE '{pfx}' AND position != 'G'
            GROUP BY game_id, game_date, team_abbr, is_home
        ) a
        JOIN (
            SELECT game_id, team_abbr, SUM(goals) AS gf
            FROM player_game_stats
            WHERE CAST(game_id AS VARCHAR) LIKE '{pfx}' AND position != 'G'
            GROUP BY game_id, team_abbr
        ) b ON b.game_id = a.game_id AND b.team_abbr != a.team_abbr
        WHERE a.team_abbr = '{abbr}'
        ORDER BY a.game_date DESC LIMIT 12
    """)

@st.cache_data(ttl=1800, show_spinner=False)
def _player_splits(pid) -> dict:
    pfx = _season_pfx()
    ha = query_fresh(f"""
        SELECT is_home,
               COUNT(*) AS gp, SUM(goals) AS g, SUM(assists) AS a,
               SUM(points) AS pts, ROUND(AVG(points),2) AS avg_pts,
               ROUND(AVG(toi_seconds/60.0),1) AS avg_toi
        FROM player_game_stats
        WHERE player_id={pid} AND is_home IS NOT NULL
          AND CAST(game_id AS VARCHAR) LIKE '{pfx}'
        GROUP BY is_home
    """)
    sit = query_fresh(f"""
        SELECT evGoals,evPoints,ppGoals,ppPoints,shGoals,shPoints,
               shots,gameWinningGoals,otGoals
        FROM skater_stats WHERE playerId={pid}
          AND season=(SELECT MAX(season) FROM games WHERE game_type=2) LIMIT 1
    """)
    return {"ha": ha, "sit": sit}

@st.cache_data(ttl=1800, show_spinner=False)
def _goalie_splits(pid) -> pd.DataFrame:
    return query_fresh(f"""
        SELECT is_home, COUNT(*) AS gp, SUM(saves) AS sv, SUM(shots_against) AS sa,
               SUM(goals_against) AS ga,
               ROUND(SUM(saves)*100.0/NULLIF(SUM(shots_against),0),2) AS sv_pct,
               ROUND(SUM(goals_against)*3600.0/NULLIF(SUM(toi_seconds),0),2) AS gaa
        FROM goalie_rolling_stats
        WHERE player_id={pid} AND is_home IS NOT NULL
          AND season=(SELECT MAX(season) FROM games WHERE game_type=2)
        GROUP BY is_home
    """)

@st.cache_data(ttl=900, show_spinner=False)
def _team_splits(abbr) -> pd.DataFrame:
    pfx = _season_pfx()
    return query_fresh(f"""
        SELECT a.is_home,
               COUNT(*) AS gp,
               SUM(CASE WHEN a.gf > b.gf THEN 1 ELSE 0 END) AS w,
               SUM(CASE WHEN a.gf = b.gf THEN 1 ELSE 0 END) AS otl,
               SUM(CASE WHEN a.gf < b.gf THEN 1 ELSE 0 END) AS l,
               ROUND(AVG(a.gf), 2) AS gf_avg,
               ROUND(AVG(b.gf), 2) AS ga_avg,
               SUM(CASE WHEN a.gf > b.gf THEN 2
                        WHEN a.gf = b.gf THEN 1 ELSE 0 END) AS pts
        FROM (
            SELECT game_id, is_home, SUM(goals) AS gf
            FROM player_game_stats
            WHERE CAST(game_id AS VARCHAR) LIKE '{pfx}' AND position != 'G'
              AND team_abbr = '{abbr}'
            GROUP BY game_id, is_home
        ) a
        JOIN (
            SELECT game_id, SUM(goals) AS gf
            FROM player_game_stats
            WHERE CAST(game_id AS VARCHAR) LIKE '{pfx}' AND position != 'G'
              AND team_abbr != '{abbr}'
            GROUP BY game_id
        ) b ON b.game_id = a.game_id
        GROUP BY a.is_home
    """)

@st.cache_data(ttl=900, show_spinner=False)
def _ai_insight(name: str, team: str) -> str:
    df = query_fresh(f"""
        SELECT headline FROM agent_insights
        WHERE team_abbr='{team}' OR entity_name ILIKE '%{name.split()[0] if name else ''}%'
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

def _stat_block(label, value, color="#fff", size=18) -> str:
    return (
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:4px;padding:5px 8px;text-align:center;">'
        f'<div style="color:#8896a8;font-size:9px;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>'
        f'<div style="color:{color};font-weight:700;font-size:{size}px;font-family:monospace;'
        f'letter-spacing:-0.02em;">{value}</div>'
        f'</div>'
    )

def _panel_header(txt):
    st.markdown(
        f"<p style='color:#8896a8;font-size:9px;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.1em;margin:10px 0 5px;border-top:1px solid rgba(255,255,255,0.06);"
        f"padding-top:8px;'>{txt}</p>",
        unsafe_allow_html=True,
    )

def _headshot_html(url, name, z_color, size=64) -> str:
    if url:
        return (
            f'<img src="{url}" style="width:{size}px;height:{size}px;border-radius:50%;'
            f'object-fit:cover;border:2px solid {z_color}55;" '
            f'onerror="this.style.display=\'none\'">'
        )
    initials = "".join(p[0] for p in name.split()[:2]) if name else "?"
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#1e2530;'
        f'border:2px solid {z_color}55;display:flex;align-items:center;justify-content:center;'
        f'font-weight:900;font-size:{size//3}px;color:#fff;flex-shrink:0;">'
        f'{initials}</div>'
    )

def _ha_compare_table(stats):
    """Render a home/away comparison table. stats = [(label, home_val, away_val, color), ...]"""
    header = """
    <div style="display:grid;grid-template-columns:76px 1fr 1fr;gap:4px;margin-bottom:4px;">
      <div></div>
      <div style="text-align:center;color:#5a8f4e;font-size:9px;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.08em;">Home</div>
      <div style="text-align:center;color:#87ceeb;font-size:9px;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.08em;">Away</div>
    </div>"""
    rows = ""
    for label, hv, av, col in stats:
        lower_better = label in ("GAA","GA","GA/g","L")
        try:
            hf = float(str(hv).replace("%","").replace("—","nan"))
            af = float(str(av).replace("%","").replace("—","nan"))
            if lower_better:
                hc = col if hf <= af else "#8896a8"
                ac = col if af < hf  else "#8896a8"
            else:
                hc = col if hf >= af else "#8896a8"
                ac = col if af > hf  else "#8896a8"
        except Exception:
            hc = ac = col
        bold = "font-weight:700;" if label in ("PTS","Avg","Sv%","GAA","GF/g","GA/g") else ""
        rows += (
            f'<div style="display:grid;grid-template-columns:76px 1fr 1fr;gap:4px;'
            f'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<div style="color:#8896a8;font-size:9px;text-transform:uppercase;'
            f'letter-spacing:0.06em;align-self:center;">{label}</div>'
            f'<div style="text-align:center;color:{hc};font-family:monospace;'
            f'font-size:13px;{bold}">{hv}</div>'
            f'<div style="text-align:center;color:{ac};font-family:monospace;'
            f'font-size:13px;{bold}">{av}</div>'
            f'</div>'
        )
    st.html(f'<div style="margin-bottom:14px;">{header}{rows}</div>')

def _quick_thesis(z: float, gp: int) -> tuple[str, str]:
    """Return (signal text, color) for the quick thesis card."""
    conf = "low sample" if gp < 10 else ("building" if gp < 20 else f"{gp}GP")
    if z >= 1.5:  return (f"Hot streak  ·  {conf}", "#f97316")
    if z >= 0.8:  return (f"Trending up  ·  {conf}", "#5a8f4e")
    if z >= 0.3:  return (f"Slightly above avg  ·  {conf}", "#5a8f4e")
    if z > -0.3:  return (f"Baseline range  ·  {conf}", "#8896a8")
    if z > -0.8:  return (f"Slightly below avg  ·  {conf}", "#8896a8")
    if z > -1.5:  return (f"Slumping  ·  {conf}", "#87ceeb")
    return (f"Cold spell  ·  {conf}", "#87ceeb")

def _style_sigma(val):
    if pd.isna(val): return "color:#8896a8"
    v = float(val)
    if v >= 1.5:  return "color:#f97316;font-weight:bold"
    if v >= 0.5:  return "color:#5a8f4e;font-weight:bold"
    if v <= -1.5: return "color:#3b82f6"
    if v <= -0.5: return "color:#87ceeb"
    return "color:#8896a8"

# ══════════════════════════════════════════════════════════════════════════════
#  TOP BAR
# ══════════════════════════════════════════════════════════════════════════════
_mode_help = {
    "Players": "Browse individual skaters and goalies",
    "Teams":   "Browse all 32 NHL teams",
    "Compare": "Compare two players or teams side by side",
}
_tab_help = {
    "Overview": "Current season form, recent games and chart",
    "Career":   "Career arc and season-by-season stats",
    "Splits":   "Home vs away and situational breakdown",
}

# Row 1 – what to browse + view (side by side)
col_browse, col_view = st.columns([3, 3])
with col_browse:
    st.markdown(
        "<p style='color:rgba(255,255,255,0.35);font-size:9px;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;margin:0 0 3px;'>"
        "What to browse</p>",
        unsafe_allow_html=True,
    )
    mc = st.columns(3)
    for i, m in enumerate(["Players", "Teams", "Compare"]):
        with mc[i]:
            active = st.session_state.t_mode == m
            if st.button(m, key=f"mode_{m}", use_container_width=True,
                         type="primary" if active else "secondary",
                         help=_mode_help[m]):
                st.session_state.t_mode        = m
                st.session_state.t_id          = None
                st.session_state.t_filter      = "All"
                st.session_state.t_filter_geo  = "All"
                st.session_state.t_filter_type = "All"
                st.session_state.t_tab         = "Overview"
                st.rerun()

with col_view:
    if st.session_state.t_mode != "Compare":
        st.markdown(
            "<p style='color:rgba(255,255,255,0.35);font-size:9px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.1em;margin:0 0 3px;'>"
            "How to view selected</p>",
            unsafe_allow_html=True,
        )
        tc = st.columns(3)
        for i, t in enumerate(["Overview", "Career", "Splits"]):
            with tc[i]:
                active = st.session_state.t_tab == t
                if st.button(t, key=f"tab_{t}", use_container_width=True,
                             type="primary" if active else "secondary",
                             help=_tab_help[t]):
                    st.session_state.t_tab = t
                    st.rerun()

# Compact tip strip below the buttons
_tip_lines = {
    "Players": "① Pick Skaters or Goalies &nbsp;·&nbsp; ② Filter by conf/division/form &nbsp;·&nbsp; ③ Click a row to see full stats →",
    "Teams":   "① Filter by conference or division &nbsp;·&nbsp; ② Click a row to see team stats →",
    "Compare": "① Pick Skaters / Goalies / Teams &nbsp;·&nbsp; ② Choose Entity A and B &nbsp;·&nbsp; ③ Stats appear side by side →",
}
tip = _tip_lines.get(st.session_state.t_mode, "")
st.markdown(
    f"<p style='color:#8896a8;font-size:10px;margin:4px 0 0;line-height:1.5;'>"
    f"<span style='color:#5a8f4e;font-weight:700;margin-right:6px;'>?</span>{tip}</p>",
    unsafe_allow_html=True,
)


mode   = st.session_state.t_mode
tab    = st.session_state.t_tab
search = st.session_state.t_search

# Sub-type row for Compare mode (Skaters / Goalies / Teams)
if mode == "Compare":
    ct = st.columns([1, 1, 1, 7])
    for i, tp in enumerate(["Skaters", "Goalies", "Teams"]):
        with ct[i]:
            active = st.session_state.t_cmp_type == tp
            if st.button(tp, key=f"cmp_type_{tp}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.t_cmp_type = tp
                st.session_state.t_cmp_a = None
                st.session_state.t_cmp_b = None
                st.rerun()
    st.markdown("<div style='height:3px;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  COMPARE MODE — full-width dual entity view
# ══════════════════════════════════════════════════════════════════════════════
if mode == "Compare":
    cmp_type = st.session_state.t_cmp_type

    # Build search list for selectboxes
    if cmp_type == "Teams":
        df_cmp_src = _team_list()
        cmp_opts = {row["abbr"]: f"{row['abbr']}  ·  {row['pts']} pts  {_z_str(row['z'])}"
                    for _, row in df_cmp_src.iterrows()}
        id_col = "abbr"
    elif cmp_type == "Goalies":
        df_cmp_src = _goalie_list()
        cmp_opts = {row["pid"]: f"{row['name']}  ·  {row['team']}  {_z_str(row['z'])}"
                    for _, row in df_cmp_src.iterrows()}
        id_col = "pid"
    else:
        df_cmp_src = _skater_list()
        cmp_opts = {row["pid"]: f"{row['name']}  ·  {row['team']}  {row['pos']}  {_z_str(row['z'])}"
                    for _, row in df_cmp_src.iterrows()}
        id_col = "pid"

    keys_list = list(cmp_opts.keys())
    labels_list = list(cmp_opts.values())

    sel_a_col, sel_b_col, cmp_ctrl_col = st.columns([4, 4, 2])
    with sel_a_col:
        idx_a = keys_list.index(st.session_state.t_cmp_a) if st.session_state.t_cmp_a in keys_list else 0
        sel_a = st.selectbox("Entity A", options=keys_list, format_func=lambda k: cmp_opts[k],
                             index=idx_a, key="cmp_sel_a")
        if sel_a != st.session_state.t_cmp_a:
            st.session_state.t_cmp_a = sel_a
            st.rerun()
    with sel_b_col:
        idx_b = keys_list.index(st.session_state.t_cmp_b) if st.session_state.t_cmp_b in keys_list else min(1, len(keys_list)-1)
        sel_b = st.selectbox("Entity B", options=keys_list, format_func=lambda k: cmp_opts[k],
                             index=idx_b, key="cmp_sel_b")
        if sel_b != st.session_state.t_cmp_b:
            st.session_state.t_cmp_b = sel_b
            st.rerun()
    with cmp_ctrl_col:
        st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
        if st.button("⇄ Swap", key="cmp_swap", use_container_width=True, help="Swap A and B"):
            st.session_state.t_cmp_a, st.session_state.t_cmp_b = (
                st.session_state.t_cmp_b, st.session_state.t_cmp_a)
            st.rerun()
        if st.button("✕ Reset", key="cmp_reset", use_container_width=True, help="Clear both selections"):
            st.session_state.t_cmp_a = None
            st.session_state.t_cmp_b = None
            st.rerun()

    id_a = st.session_state.t_cmp_a or keys_list[0]
    id_b = st.session_state.t_cmp_b or keys_list[min(1, len(keys_list)-1)]

    row_a = df_cmp_src[df_cmp_src[id_col] == id_a].iloc[0] if not df_cmp_src[df_cmp_src[id_col] == id_a].empty else None
    row_b = df_cmp_src[df_cmp_src[id_col] == id_b].iloc[0] if not df_cmp_src[df_cmp_src[id_col] == id_b].empty else None

    if row_a is None or row_b is None:
        st.info("Select two entities to compare.")
        st.stop()

    zca, zcb = _z_color(row_a["z"]), _z_color(row_b["z"])

    st.markdown("<hr style='border-color:rgba(255,255,255,0.08);margin:6px 0;'>", unsafe_allow_html=True)

    # ── Bio headers ────────────────────────────────────────────────────────────
    col_a, col_vs, col_b = st.columns([5, 1, 5])

    def _cmp_bio_html(row, zc, is_player=True, is_goalie=False):
        pid = int(row["pid"]) if is_player else None
        bio = _player_bio(pid) if is_player else None
        hs  = str(bio["headshot"]) if (bio is not None and bio["headshot"]) else ""
        img = _headshot_html(hs, row["name"] if is_player else row["abbr"], zc, 56)
        if is_player:
            pos_team = f"{row.get('pos','G')} · {row['team']}"
            name_str = row["name"]
        else:
            _dm2 = {"A":"Atlantic","M":"Metropolitan","C":"Central","P":"Pacific"}
            pos_team = _dm2.get(str(row.get("div","")), "—") + " Div"
            name_str = row["abbr"]
        return f"""
        <div style="display:flex;align-items:center;gap:12px;
                    background:rgba(255,255,255,0.02);border:1px solid {zc}33;
                    border-radius:6px;padding:12px;">
          {img}
          <div style="flex:1;">
            <div style="color:#fff;font-weight:800;font-size:16px;letter-spacing:-0.02em;">{name_str}</div>
            <div style="color:#8896a8;font-size:11px;margin-top:2px;">{pos_team}</div>
            <div style="color:{zc};font-weight:900;font-size:20px;font-family:monospace;margin-top:4px;">{_z_str(row['z'])}</div>
          </div>
        </div>"""

    with col_a:
        st.html(_cmp_bio_html(row_a, zca, is_player=(cmp_type != "Teams")))
    with col_vs:
        st.html("<div style='text-align:center;color:rgba(255,255,255,0.2);font-size:18px;"
                "font-weight:900;margin-top:20px;'>VS</div>")
    with col_b:
        st.html(_cmp_bio_html(row_b, zcb, is_player=(cmp_type != "Teams")))

    # ── Stat comparison table ───────────────────────────────────────────────────
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    if cmp_type == "Teams":
        cmp_stats = [
            ("GP",    row_a["gp"],   row_b["gp"],   "#8896a8"),
            ("PTS",   row_a["pts"],  row_b["pts"],  "#5a8f4e"),
            ("W",     row_a["w"],    row_b["w"],    "#5a8f4e"),
            ("L",     row_a["l"],    row_b["l"],    "#c41e3a"),
            ("DIFF",  int(row_a["diff"]) if pd.notna(row_a["diff"]) else "—",
                      int(row_b["diff"]) if pd.notna(row_b["diff"]) else "—",  "#fff"),
            ("PP%",   f"{float(row_a['pp_pct']):.1f}%" if pd.notna(row_a['pp_pct']) else "—",
                      f"{float(row_b['pp_pct']):.1f}%" if pd.notna(row_b['pp_pct']) else "—",  "#f97316"),
            ("PK%",   f"{float(row_a['pk_pct']):.1f}%" if pd.notna(row_a['pk_pct']) else "—",
                      f"{float(row_b['pk_pct']):.1f}%" if pd.notna(row_b['pk_pct']) else "—",  "#87ceeb"),
            ("Momentum",_z_str(row_a["z"]), _z_str(row_b["z"]), "#8896a8"),
        ]
    elif cmp_type == "Goalies":
        sv_a = float(row_a["sv_pct"]) if pd.notna(row_a["sv_pct"]) else 0
        sv_b = float(row_b["sv_pct"]) if pd.notna(row_b["sv_pct"]) else 0
        cmp_stats = [
            ("GP",    int(row_a["gp"]),  int(row_b["gp"]),  "#8896a8"),
            ("W",     int(row_a["w"]) if pd.notna(row_a["w"]) else "—",
                      int(row_b["w"]) if pd.notna(row_b["w"]) else "—",  "#5a8f4e"),
            ("Sv%",   f"{sv_a:.2f}%",   f"{sv_b:.2f}%",   "#f97316"),
            ("GAA",   f"{float(row_a['gaa']):.2f}" if pd.notna(row_a['gaa']) else "—",
                      f"{float(row_b['gaa']):.2f}" if pd.notna(row_b['gaa']) else "—",  "#5a8f4e"),
            ("SO",    int(row_a["so"]) if pd.notna(row_a["so"]) else 0,
                      int(row_b["so"]) if pd.notna(row_b["so"]) else 0, "#8896a8"),
            ("Sv%/5g",f"{float(row_a['sv5']):.2f}%", f"{float(row_b['sv5']):.2f}%", "#f97316"),
            ("Momentum",_z_str(row_a["z"]), _z_str(row_b["z"]), "#8896a8"),
        ]
    else:  # Skaters
        pm_a = (f"+{int(row_a['pm'])}" if row_a['pm']>0 else str(int(row_a['pm']))) if pd.notna(row_a['pm']) else "—"
        pm_b = (f"+{int(row_b['pm'])}" if row_b['pm']>0 else str(int(row_b['pm']))) if pd.notna(row_b['pm']) else "—"
        cmp_stats = [
            ("GP",    int(row_a["gp"]),  int(row_b["gp"]),  "#8896a8"),
            ("G",     int(row_a["g"]),   int(row_b["g"]),   "#fff"),
            ("A",     int(row_a["a"]),   int(row_b["a"]),   "#8896a8"),
            ("PTS",   int(row_a["pts"]), int(row_b["pts"]), "#5a8f4e"),
            ("+/-",   pm_a,              pm_b,              "#fff"),
            ("PPP",   int(row_a["ppp"]) if pd.notna(row_a["ppp"]) else "—",
                      int(row_b["ppp"]) if pd.notna(row_b["ppp"]) else "—", "#87ceeb"),
            ("5g avg",f"{row_a['avg5']:.2f}", f"{row_b['avg5']:.2f}", "#f97316"),
            ("Ice Time", f"{row_a['toi']:.1f}" if pd.notna(row_a['toi']) else "—",
                      f"{row_b['toi']:.1f}" if pd.notna(row_b['toi']) else "—", "#8896a8"),
            ("Momentum",_z_str(row_a["z"]), _z_str(row_b["z"]), "#8896a8"),
        ]

    # Render comparison as colored table
    rows_html = ""
    _cmp_a_leads = 0
    _cmp_b_leads = 0
    for stat_label, va, vb, col in cmp_stats:
        lower_better = stat_label in ("GAA", "L")
        try:
            fa = float(str(va).replace("%","").replace("+","").replace("σ","").replace("—","nan"))
            fb = float(str(vb).replace("%","").replace("+","").replace("σ","").replace("—","nan"))
            if lower_better:
                ca = col if fa <= fb else "#8896a8"
                cb = col if fb < fa  else "#8896a8"
            else:
                ca = col if fa >= fb else "#8896a8"
                cb = col if fb > fa  else "#8896a8"
            if ca != "#8896a8" and cb == "#8896a8": _cmp_a_leads += 1
            elif cb != "#8896a8" and ca == "#8896a8": _cmp_b_leads += 1
        except Exception:
            ca = cb = col
        bold = "font-weight:700;" if stat_label in ("PTS","Sv%","Momentum","5g avg") else ""
        rows_html += (
            f'<div style="display:grid;grid-template-columns:1fr 90px 1fr;'
            f'padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<div style="text-align:right;color:{ca};font-family:monospace;'
            f'font-size:14px;{bold}padding-right:12px;">{va}</div>'
            f'<div style="text-align:center;color:#8896a8;font-size:9px;text-transform:uppercase;'
            f'letter-spacing:0.06em;align-self:center;">{stat_label}</div>'
            f'<div style="text-align:left;color:{cb};font-family:monospace;'
            f'font-size:14px;{bold}padding-left:12px;">{vb}</div>'
            f'</div>'
        )
    _cmp_total = _cmp_a_leads + _cmp_b_leads
    _cmp_footer = (
        f'<div style="display:grid;grid-template-columns:1fr 90px 1fr;padding:8px 0;'
        f'margin-top:4px;border-top:1px solid rgba(255,255,255,0.08);">'
        f'<div style="text-align:right;padding-right:12px;">'
        f'<span style="color:{zca};font-weight:700;font-size:12px;">{_cmp_a_leads}</span>'
        f'<span style="color:#8896a8;font-size:10px;"> stat{"s" if _cmp_a_leads != 1 else ""} won</span></div>'
        f'<div style="text-align:center;color:#8896a8;font-size:9px;align-self:center;">of {_cmp_total}</div>'
        f'<div style="text-align:left;padding-left:12px;">'
        f'<span style="color:{zcb};font-weight:700;font-size:12px;">{_cmp_b_leads}</span>'
        f'<span style="color:#8896a8;font-size:10px;"> stat{"s" if _cmp_b_leads != 1 else ""} won</span></div>'
        f'</div>'
    )

    # Header
    name_a = row_a["name"] if cmp_type != "Teams" else row_a["abbr"]
    name_b = row_b["name"] if cmp_type != "Teams" else row_b["abbr"]
    st.html(
        f'<div style="display:grid;grid-template-columns:1fr 90px 1fr;'
        f'padding:5px 0;margin-bottom:4px;">'
        f'<div style="text-align:right;color:{zca};font-size:10px;font-weight:700;padding-right:12px;">{name_a}</div>'
        f'<div></div>'
        f'<div style="text-align:left;color:{zcb};font-size:10px;font-weight:700;padding-left:12px;">{name_b}</div>'
        f'</div>'
        f'<div style="margin-bottom:8px;">{rows_html}</div>'
        f'{_cmp_footer}'
    )

    # ── Overlaid form chart (skaters/goalies) ───────────────────────────────────
    if cmp_type in ("Skaters", "Goalies") and cmp_type != "Teams":
        _panel_header("Momentum — rolling 5-game average")
        if cmp_type == "Skaters":
            dfa = _player_form_series(int(id_a))
            dfb = _player_form_series(int(id_b))
            if not dfa.empty and not dfb.empty:
                dfa["roll5"] = dfa["pts"].rolling(5, min_periods=2).mean()
                dfb["roll5"] = dfb["pts"].rolling(5, min_periods=2).mean()
                fig = go.Figure()
                fig.add_scatter(x=dfa["date"].astype(str).str[:10], y=dfa["roll5"],
                                mode="lines", line=dict(color=zca, width=2),
                                name=name_a, hovertemplate="%{x}: %{y:.2f}<extra></extra>")
                fig.add_scatter(x=dfb["date"].astype(str).str[:10], y=dfb["roll5"],
                                mode="lines", line=dict(color=zcb, width=2, dash="dot"),
                                name=name_b, hovertemplate="%{x}: %{y:.2f}<extra></extra>")
                layout = dict(**CHART_BASE)
                layout["height"] = 220
                layout["legend"] = dict(orientation="h", y=1.1, font=dict(size=9))
                fig.update_layout(**layout)
                fig.update_xaxes(tickangle=45, nticks=12)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            dfa = _goalie_games(int(id_a))
            dfb = _goalie_games(int(id_b))
            if not dfa.empty and not dfb.empty:
                fig = go.Figure()
                fig.add_scatter(x=dfa["date"].astype(str).str[:10], y=dfa["sv_pct"],
                                mode="lines+markers", line=dict(color=zca, width=2),
                                name=name_a, hovertemplate="%{x}: %{y:.2f}%<extra></extra>")
                fig.add_scatter(x=dfb["date"].astype(str).str[:10], y=dfb["sv_pct"],
                                mode="lines+markers", line=dict(color=zcb, width=2, dash="dot"),
                                name=name_b, hovertemplate="%{x}: %{y:.2f}%<extra></extra>")
                layout = dict(**CHART_BASE)
                layout["height"] = 200
                layout["legend"] = dict(orientation="h", y=1.1, font=dict(size=9))
                fig.update_layout(**layout)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    elif cmp_type == "Teams":
        _panel_header("Recent form — goals for per game (10-game rolling)")
        df_ta = _team_games(id_a)
        df_tb = _team_games(id_b)
        if not df_ta.empty and not df_tb.empty:
            fig = go.Figure()
            fig.add_bar(x=df_ta["date"].astype(str).str[:10], y=df_ta["GF"],
                        name=f"{id_a} GF", marker_color=zca, opacity=0.8,
                        hovertemplate="%{x}: %{y} GF<extra></extra>")
            fig.add_bar(x=df_tb["date"].astype(str).str[:10], y=df_tb["GF"],
                        name=f"{id_b} GF", marker_color=zcb, opacity=0.6,
                        hovertemplate="%{x}: %{y} GF<extra></extra>")
            layout = dict(**CHART_BASE)
            layout["height"] = 200
            layout["barmode"] = "group"
            layout["legend"] = dict(orientation="h", y=1.1, font=dict(size=9))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD FILTERED LIST  (Players / Teams modes)
# ══════════════════════════════════════════════════════════════════════════════
# Sub-mode chips + search on same row
if mode == "Players":
    sub_chips = ["Skaters", "Goalies"]
    sc_left, sc_right = st.columns([3, 5])
    with sc_left:
        sc = st.columns(2)
        for i, s in enumerate(sub_chips):
            with sc[i]:
                active = st.session_state.t_sub == s
                if st.button(s, key=f"sub_{s}", use_container_width=True,
                             type="primary" if active else "secondary"):
                    st.session_state.t_sub        = s
                    st.session_state.t_id         = None
                    st.session_state.t_filter     = "All"
                    st.session_state.t_filter_geo  = "All"
                    st.session_state.t_filter_type = "All"
                    st.rerun()
    with sc_right:
        st.session_state.t_search = st.text_input(
            "", placeholder="🔍  Search player…",
            label_visibility="collapsed",
            value=st.session_state.t_search,
            key="t_search_input",
        )
else:
    # Teams mode – search on its own
    _, search_col = st.columns([3, 5])
    with search_col:
        st.session_state.t_search = st.text_input(
            "", placeholder="🔍  Search team…",
            label_visibility="collapsed",
            value=st.session_state.t_search,
            key="t_search_input",
        )

st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)

# Filter dropdowns — Conf/Div + Player-type (skaters only)
_GEO_OPTS  = ["All","East","West","ATL","MET","CEN","PAC"]
_TYPE_OPTS = ["All","Fwd","Def","Hot","Cold"]
_GEO_LABELS  = {"All":"All teams","East":"East Conf","West":"West Conf",
                "ATL":"Atlantic","MET":"Metropolitan","CEN":"Central","PAC":"Pacific"}
_TYPE_LABELS = {"All":"All positions","Fwd":"Forwards","Def":"Defenders",
                "Hot":"Hot (σ ≥ 0.8)","Cold":"Cold (σ ≤ −0.8)"}
_show_type_flt = (mode == "Players" and st.session_state.t_sub == "Skaters")

_fd1, _fd2, _fd3 = st.columns([3, 3, 2])
with _fd1:
    _new_geo = st.selectbox(
        "Conf/Division", _GEO_OPTS,
        index=_GEO_OPTS.index(st.session_state.t_filter_geo) if st.session_state.t_filter_geo in _GEO_OPTS else 0,
        format_func=lambda x: _GEO_LABELS.get(x, x),
        label_visibility="collapsed", key="t_filter_geo_sel",
    )
    if _new_geo != st.session_state.t_filter_geo:
        st.session_state.t_filter_geo = _new_geo
        st.rerun()
if _show_type_flt:
    with _fd2:
        _new_type = st.selectbox(
            "Player Type", _TYPE_OPTS,
            index=_TYPE_OPTS.index(st.session_state.t_filter_type) if st.session_state.t_filter_type in _TYPE_OPTS else 0,
            format_func=lambda x: _TYPE_LABELS.get(x, x),
            label_visibility="collapsed", key="t_filter_type_sel",
        )
        if _new_type != st.session_state.t_filter_type:
            st.session_state.t_filter_type = _new_type
            st.rerun()

st.markdown("<div style='height:3px;border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:5px;'></div>",
            unsafe_allow_html=True)

_flt_geo  = st.session_state.t_filter_geo
_flt_type = st.session_state.t_filter_type

if mode == "Players":
    if st.session_state.t_sub == "Skaters":
        df_src = _skater_list()
        if _flt_geo in DIV_TEAMS:   df_src = df_src[df_src["team"].isin(DIV_TEAMS[_flt_geo])]
        elif _flt_geo == "East":    df_src = df_src[df_src["team"].isin(EAST)]
        elif _flt_geo == "West":    df_src = df_src[df_src["team"].isin(WEST)]
        if _flt_type == "Fwd":      df_src = df_src[df_src["pos"].isin(["C","L","R"])]
        elif _flt_type == "Def":    df_src = df_src[df_src["pos"] == "D"]
        elif _flt_type == "Hot":    df_src = df_src[df_src["z"] >= 0.8]
        elif _flt_type == "Cold":   df_src = df_src[df_src["z"] <= -0.8]
    else:
        df_src = _goalie_list()
        if _flt_geo in DIV_TEAMS:   df_src = df_src[df_src["team"].isin(DIV_TEAMS[_flt_geo])]
        elif _flt_geo == "East":    df_src = df_src[df_src["team"].isin(EAST)]
        elif _flt_geo == "West":    df_src = df_src[df_src["team"].isin(WEST)]
else:
    df_src = _team_list()
    if _flt_geo == "East":          df_src = df_src[df_src["conf"] == "E"]
    elif _flt_geo == "West":        df_src = df_src[df_src["conf"] == "W"]
    elif _flt_geo in DIV_TEAMS:
        _dmap = {"ATL":"A","MET":"M","CEN":"C","PAC":"P"}
        df_src = df_src[df_src["div"] == _dmap[_flt_geo]]

if search:
    q = search.lower()
    if mode == "Teams":
        df_src = df_src[df_src["abbr"].str.lower().str.contains(q, na=False)]
    else:
        df_src = df_src[
            df_src["name"].str.lower().str.contains(q, na=False) |
            df_src["team"].str.lower().str.contains(q, na=False)
        ]

df_src = df_src.reset_index(drop=True)

# ── Sort left list ───────────────────────────────────────────────────────────
_SORT_OPTS_SKATER = {"z": "Momentum", "pts": "PTS", "avg5": "5g avg", "gp": "GP"}
_SORT_OPTS_GOALIE = {"z": "Momentum", "sv_pct": "Sv%", "gp": "GP"}
_SORT_OPTS_TEAM   = {"z": "Momentum", "pts": "PTS"}

_is_goalie_pre = (mode == "Players" and st.session_state.t_sub == "Goalies")
_sort_opts_now = (_SORT_OPTS_GOALIE if _is_goalie_pre else
                  _SORT_OPTS_TEAM   if mode == "Teams"  else
                  _SORT_OPTS_SKATER)

if st.session_state.t_sort not in _sort_opts_now:
    st.session_state.t_sort = list(_sort_opts_now.keys())[0]

if not df_src.empty and st.session_state.t_sort in df_src.columns:
    df_src = df_src.sort_values(st.session_state.t_sort, ascending=False).reset_index(drop=True)

# Auto-select top entity
if st.session_state.t_id is None and not df_src.empty:
    st.session_state.t_id = df_src.iloc[0]["abbr" if mode == "Teams" else "pid"]

# ══════════════════════════════════════════════════════════════════════════════
#  3-PANEL LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
col_left, col_center, col_right = st.columns([1.7, 3.7, 1.6], gap="small")

# ─────────────────────────────────────────────────────────────────────────────
#  LEFT PANEL
# ─────────────────────────────────────────────────────────────────────────────
with col_left:
    # Sort + count row
    _lbl_mode = ('SKATERS' if mode=='Players' and st.session_state.t_sub=='Skaters'
                 else 'GOALIES' if mode=='Players' else 'TEAMS')
    _sort_label_col, _sort_sel_col = st.columns([3, 4])
    with _sort_label_col:
        st.markdown(
            f"<p style='color:#8896a8;font-size:10px;margin:6px 0 0;font-family:monospace;'>"
            f"NHL · {_lbl_mode} · {len(df_src)}</p>",
            unsafe_allow_html=True,
        )
    with _sort_sel_col:
        _new_sort = st.selectbox(
            "Sort", list(_sort_opts_now.keys()),
            format_func=lambda x: _sort_opts_now[x],
            index=list(_sort_opts_now.keys()).index(st.session_state.t_sort),
            label_visibility="collapsed", key="t_sort_select",
        )
        if _new_sort != st.session_state.t_sort:
            st.session_state.t_sort = _new_sort
            st.rerun()

    is_goalie_mode = (mode == "Players" and st.session_state.t_sub == "Goalies")

    # Sort value column label + data
    _sort_col_now = st.session_state.t_sort
    _sort_col_label = _sort_opts_now.get(_sort_col_now, _sort_col_now)

    if mode == "Players" and not is_goalie_mode:
        df_disp = df_src[["name","team", _sort_col_now]].copy()
        df_disp["_name"] = df_disp["name"] + "  ·  " + df_disp["team"]
        df_disp = df_disp[["_name", _sort_col_now]].copy()
        df_disp.columns = ["Player", _sort_col_label]
        col_cfg = {
            "Player":         st.column_config.TextColumn("Player", width="medium"),
            _sort_col_label:  st.column_config.NumberColumn(_sort_col_label, width="small", format="%.2f"),
        }
    elif is_goalie_mode:
        df_disp = df_src[["name","team", _sort_col_now]].copy()
        df_disp["_name"] = df_disp["name"] + "  ·  " + df_disp["team"]
        df_disp = df_disp[["_name", _sort_col_now]].copy()
        df_disp.columns = ["Goalie", _sort_col_label]
        col_cfg = {
            "Goalie":         st.column_config.TextColumn("Goalie", width="medium"),
            _sort_col_label:  st.column_config.NumberColumn(_sort_col_label, width="small", format="%.2f"),
        }
    else:
        df_disp = df_src[["abbr", _sort_col_now]].copy()
        df_disp.columns = ["Team", _sort_col_label]
        col_cfg = {
            "Team":           st.column_config.TextColumn("Team", width="medium"),
            _sort_col_label:  st.column_config.NumberColumn(_sort_col_label, width="small", format="%.2f"),
        }

    _sigma_col = _sort_col_label if _sort_col_label in df_disp.columns else None
    styled = df_disp.style.applymap(_style_sigma, subset=[_sigma_col]) if _sigma_col else df_disp.style

    _tbl_h = min(520, max(180, len(df_src) * 30 + 42))

    event = st.dataframe(
        styled,
        column_config=col_cfg,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        height=_tbl_h,
        hide_index=True,
    )

    if event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        if idx < len(df_src):
            new_id = df_src.iloc[idx]["abbr" if mode == "Teams" else "pid"]
            if st.session_state.t_id != new_id:
                st.session_state.t_id = new_id
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  CENTER PANEL
# ─────────────────────────────────────────────────────────────────────────────
with col_center:
    sel_id = st.session_state.t_id
    if sel_id is None:
        st.markdown("<p style='color:#8896a8;margin-top:60px;text-align:center;'>Select an entity</p>",
                    unsafe_allow_html=True)
    else:
        # ══════════════════════════════════════════════════════════════════════
        #  SKATER CENTER
        # ══════════════════════════════════════════════════════════════════════
        if mode == "Players" and not is_goalie_mode:
            row = df_src[df_src["pid"] == sel_id]
            if row.empty:
                st.info("Player not found in current filter.")
            else:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))

                # Bio strip
                if bio is not None:
                    h_cm = int(bio["heightInCentimeters"]) if bio["heightInCentimeters"] else 0
                    w_kg = int(bio["weightInKilograms"])   if bio["weightInKilograms"]   else 0
                    feet, inch = divmod(round(h_cm/2.54), 12)
                    lbs  = round(w_kg*2.205)
                    birth= str(bio["birthDate"])[:10] if bio["birthDate"] else "—"
                    num  = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    hs   = str(bio["headshot"]) if bio["headshot"] else ""
                    img  = _headshot_html(hs, row["name"], zc, 50)
                    st.html(f"""
                    <div style="display:flex;align-items:center;gap:14px;
                                border-bottom:1px solid rgba(255,255,255,0.08);
                                padding-bottom:9px;margin-bottom:8px;">
                      {img}
                      <div style="flex:1;">
                        <div style="color:#fff;font-weight:800;font-size:17px;
                                    letter-spacing:-0.02em;">{row['name']}</div>
                        <div style="color:#8896a8;font-size:10px;margin-top:1px;">
                          #{num} · {row['pos']} · {row['team']} ·
                          {feet}'{inch}" · {lbs} lbs · b. {birth[:4] if birth != '—' else '—'}
                        </div>
                      </div>
                      <div style="text-align:right;">
                        <div style="color:{zc};font-weight:900;font-size:22px;
                                    font-family:monospace;">{_z_str(row['z'])}</div>
                        <div style="color:#8896a8;font-size:9px;">5g vs 20g</div>
                      </div>
                    </div>""")

                # Summary metric bar (Börsdata style)
                pm   = row["pm"]
                pm_s = (f"+{int(pm)}" if pm > 0 else str(int(pm))) if pd.notna(pm) else "—"
                pm_c = "#5a8f4e" if (pd.notna(pm) and pm > 0) else ("#c41e3a" if (pd.notna(pm) and pm < 0) else "#8896a8")
                toi  = f'{row["toi"]:.1f}' if pd.notna(row["toi"]) else "—"
                ppp  = int(row["ppp"]) if pd.notna(row["ppp"]) else "—"
                sh   = f'{row["sh_pct"]:.1f}%' if pd.notna(row["sh_pct"]) else "—"

                sb_cols = st.columns(7)
                summary = [
                    ("GP",    int(row["gp"]),        "#8896a8"),
                    ("G",     int(row["g"]),          "#fff"),
                    ("A",     int(row["a"]),          "#8896a8"),
                    ("PTS",   int(row["pts"]),        "#5a8f4e"),
                    ("+/-",   pm_s,                   pm_c),
                    ("PPP",   ppp,                    "#87ceeb"),
                    ("Ice Time", toi,                "#8896a8"),
                ]
                for i,(lbl,val,col) in enumerate(summary):
                    with sb_cols[i]:
                        st.html(_stat_block(lbl, val, col, 16))

                sb2 = st.columns(4)
                summary2 = [
                    ("5g avg", f"{row['avg5']:.2f}", "#f97316"),
                    ("SH%",    sh,                    "#8896a8"),
                    ("FO%",    f'{row["fo_pct"]:.1f}%' if (pd.notna(row["fo_pct"]) and float(row["fo_pct"]) > 0) else "—", "#8896a8"),
                    ("Form σ", _z_str(row["z"]),      zc),
                ]
                for i,(lbl,val,col) in enumerate(summary2):
                    with sb2[i]:
                        st.html(_stat_block(lbl, val, col, 15))

                # ── OVERVIEW TAB ──────────────────────────────────────────────
                if tab == "Overview":
                    # Chart range toggle
                    _cr_opts = ["L10", "L20", "L40", "Season"]
                    _cr_cols = st.columns([1, 1, 1, 1, 4])
                    for _ci, _cr_opt in enumerate(_cr_opts):
                        with _cr_cols[_ci]:
                            _cr_active = st.session_state.t_chart_range == _cr_opt
                            if st.button(_cr_opt, key=f"cr_{_cr_opt}_{sel_id}", use_container_width=True,
                                         type="primary" if _cr_active else "secondary"):
                                st.session_state.t_chart_range = _cr_opt
                                st.rerun()

                    df_form = _player_form_series(int(sel_id))
                    if not df_form.empty:
                        df_form = df_form.copy()
                        # Apply window filter before computing rolling averages
                        _cr_sel = st.session_state.t_chart_range
                        if _cr_sel == "L10":    df_form = df_form.tail(10).reset_index(drop=True)
                        elif _cr_sel == "L20":  df_form = df_form.tail(20).reset_index(drop=True)
                        elif _cr_sel == "L40":  df_form = df_form.tail(40).reset_index(drop=True)
                        df_form["roll5"]  = df_form["pts"].rolling(5, min_periods=2).mean()
                        df_form["roll10"] = df_form["pts"].rolling(10, min_periods=5).mean()
                        season_avg = df_form["pts"].mean()

                        fig = go.Figure()
                        bar_colors = [
                            _z_color(1.6) if p >= 2 else (_z_color(0.6) if p == 1 else "rgba(255,255,255,0.10)")
                            for p in df_form["pts"]
                        ]
                        fig.add_bar(
                            x=df_form["date"].astype(str).str[:10], y=df_form["pts"],
                            marker_color=bar_colors, name="Points",
                            hovertemplate="%{x}: %{y} pts<extra></extra>",
                        )
                        fig.add_scatter(
                            x=df_form["date"].astype(str).str[:10], y=df_form["roll5"],
                            mode="lines", line=dict(color="#f97316", width=2),
                            name="5g avg", hovertemplate="%{x}: %{y:.2f}<extra></extra>",
                        )
                        fig.add_scatter(
                            x=df_form["date"].astype(str).str[:10], y=df_form["roll10"],
                            mode="lines", line=dict(color="#87ceeb", width=1.5, dash="dot"),
                            name="10g avg", hovertemplate="%{x}: %{y:.2f}<extra></extra>",
                        )
                        fig.add_hline(y=season_avg, line_dash="dot",
                                      line_color="rgba(255,255,255,0.15)",
                                      annotation_text=f"avg {season_avg:.2f}",
                                      annotation_font_size=8,
                                      annotation_font_color="rgba(255,255,255,0.3)")
                        layout = dict(**CHART_BASE)
                        layout["height"] = 220
                        layout["legend"] = dict(orientation="h", y=1.08, font=dict(size=9))
                        fig.update_layout(**layout)
                        fig.update_xaxes(tickangle=45, nticks=14)
                        st.plotly_chart(fig, use_container_width=True,
                                        config={"displayModeBar": False})

                    # Mini KPI bars — career season progression (Börsdata style)
                    df_car = _player_career(int(sel_id))
                    if not df_car.empty and len(df_car) >= 2:
                        _panel_header("Career progression")
                        fig_kpi = make_subplots(rows=1, cols=4, shared_yaxes=False,
                                                subplot_titles=["Goals","Assists","PTS","PTS/82"],
                                                horizontal_spacing=0.08)
                        kpi_data = [
                            (df_car["goals"],    "Goals",    1),
                            (df_car["assists"],  "Assists",  2),
                            (df_car["points"],   "PTS",      3),
                            (df_car["pts_per_82"],"PTS/82",  4),
                        ]
                        for series, name, col_idx in kpi_data:
                            colors = ["#5a8f4e"] * (len(series)-1) + ["#f97316"]
                            fig_kpi.add_bar(
                                x=df_car["season_label"], y=series,
                                marker_color=colors, name=name,
                                showlegend=False, row=1, col=col_idx,
                                hovertemplate="%{x}: %{y}<extra></extra>",
                                text=series.round(0).astype(int).astype(str),
                                textposition="outside",
                                textfont=dict(size=8, color="#8896a8"),
                            )
                        fig_kpi.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#8896a8", size=8),
                            margin=dict(l=0, r=0, t=24, b=0),
                            height=140,
                            hoverlabel=dict(bgcolor="#111", font_color="#f1f5f9"),
                        )
                        fig_kpi.update_xaxes(tickfont=dict(size=7), tickangle=45,
                                             showgrid=False, nticks=5)
                        fig_kpi.update_yaxes(showgrid=False, showticklabels=False)
                        for ann in fig_kpi.layout.annotations:
                            ann.font.size = 9
                            ann.font.color = "#8896a8"
                        st.plotly_chart(fig_kpi, use_container_width=True,
                                        config={"displayModeBar": False})

                # ── CAREER TAB ────────────────────────────────────────────────
                elif tab == "Career":
                    gate("deep_dive_career", "Career & Splits",
                         "Karriärdata för alla 16 säsonger tillgängligt på Base-plan.")
                    df_car = _player_career(int(sel_id))
                    if not df_car.empty:
                        fig_arc = go.Figure()
                        fig_arc.add_scatter(
                            x=df_car["season_label"], y=df_car["pts_per_82"],
                            mode="lines+markers",
                            line=dict(color="#5a8f4e", width=2),
                            marker=dict(size=5),
                            fill="tozeroy", fillcolor="rgba(90,143,78,0.06)",
                            name="PTS/82",
                            hovertemplate="%{x}: %{y:.0f} PTS/82<extra></extra>",
                        )
                        layout_arc = dict(**CHART_BASE)
                        layout_arc["height"] = 170
                        layout_arc["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)",
                                                   tickfont=dict(size=9), title="PTS/82")
                        fig_arc.update_layout(**layout_arc)
                        fig_arc.update_xaxes(type="category", tickangle=45, nticks=10)
                        st.plotly_chart(fig_arc, use_container_width=True,
                                        config={"displayModeBar": False})

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
                            f'<table style="width:100%;border-collapse:collapse;margin-top:6px;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Season</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">GP</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">G</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:right;">A</th>'
                            f'<th style="padding:4px 6px;color:#5a8f4e;font-size:9px;text-align:right;">PTS</th>'
                            f'<th style="padding:4px 10px;color:#f97316;font-size:9px;text-align:right;">PTS/82</th>'
                            f'</tr></thead><tbody>{rows}</tbody></table>'
                        )

                # ── SPLITS TAB ────────────────────────────────────────────────
                elif tab == "Splits":
                    gate("deep_dive_splits", "Home / Away Splits",
                         "Situationsdata och hemma/borta-splits ingår i Base-plan.")
                    splits = _player_splits(int(sel_id))
                    ha_df  = splits["ha"]
                    sit_df = splits["sit"]

                    _panel_header("Home vs Away — current season")
                    home_row = ha_df[ha_df["is_home"] == True]
                    away_row = ha_df[ha_df["is_home"] == False]
                    h = home_row.iloc[0] if not home_row.empty else None
                    a = away_row.iloc[0] if not away_row.empty else None

                    def _hv(r, col, fmt=None):
                        if r is None or pd.isna(r[col]): return "—"
                        v = r[col]; return fmt(v) if fmt else str(int(v))

                    _ha_compare_table([
                        ("GP",  _hv(h,"gp"),                      _hv(a,"gp"),                      "#8896a8"),
                        ("G",   _hv(h,"g"),                       _hv(a,"g"),                       "#fff"),
                        ("A",   _hv(h,"a"),                       _hv(a,"a"),                       "#8896a8"),
                        ("PTS", _hv(h,"pts"),                     _hv(a,"pts"),                     "#5a8f4e"),
                        ("Avg", _hv(h,"avg_pts",lambda v:f"{v:.2f}"), _hv(a,"avg_pts",lambda v:f"{v:.2f}"), "#f97316"),
                        ("Ice Time", _hv(h,"avg_toi",lambda v:f"{v:.1f}"), _hv(a,"avg_toi",lambda v:f"{v:.1f}"), "#8896a8"),
                    ])

                    _panel_header("Situation — current season")
                    if not sit_df.empty:
                        s = sit_df.iloc[0]
                        def _sv(col): return str(int(s[col])) if pd.notna(s[col]) else "—"
                        st.html(f"""
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px;">
                          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                      border-radius:4px;padding:9px;text-align:center;">
                            <div style="color:#8896a8;font-size:9px;text-transform:uppercase;margin-bottom:5px;">Even Str.</div>
                            <div style="color:#fff;font-size:18px;font-weight:900;font-family:monospace;">{_sv("evPoints")}</div>
                            <div style="color:#8896a8;font-size:9px;">{_sv("evGoals")} G</div>
                          </div>
                          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(247,151,22,0.25);
                                      border-radius:4px;padding:9px;text-align:center;">
                            <div style="color:#f97316;font-size:9px;text-transform:uppercase;margin-bottom:5px;">Power Play</div>
                            <div style="color:#f97316;font-size:18px;font-weight:900;font-family:monospace;">{_sv("ppPoints")}</div>
                            <div style="color:#8896a8;font-size:9px;">{_sv("ppGoals")} G</div>
                          </div>
                          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(135,206,235,0.2);
                                      border-radius:4px;padding:9px;text-align:center;">
                            <div style="color:#87ceeb;font-size:9px;text-transform:uppercase;margin-bottom:5px;">Shorthanded</div>
                            <div style="color:#87ceeb;font-size:18px;font-weight:900;font-family:monospace;">{_sv("shPoints")}</div>
                            <div style="color:#8896a8;font-size:9px;">{_sv("shGoals")} G</div>
                          </div>
                        </div>
                        <div style="display:flex;gap:8px;">
                          {_stat_block('Shots', _sv('shots'), '#8896a8', 13)}
                          {_stat_block('GWG', _sv('gameWinningGoals'), '#5a8f4e', 13)}
                          {_stat_block('OTG', _sv('otGoals'), '#f97316', 13)}
                        </div>""")

        # ══════════════════════════════════════════════════════════════════════
        #  GOALIE CENTER
        # ══════════════════════════════════════════════════════════════════════
        elif mode == "Players" and is_goalie_mode:
            row = df_src[df_src["pid"] == sel_id]
            if row.empty:
                st.info("Goalie not found.")
            else:
                row = row.iloc[0]
                zc  = _z_color(row["z"])
                bio = _player_bio(int(sel_id))

                if bio is not None:
                    hs  = str(bio["headshot"]) if bio["headshot"] else ""
                    num = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    img = _headshot_html(hs, row["name"], zc, 50)
                    st.html(f"""
                    <div style="display:flex;align-items:center;gap:14px;
                                border-bottom:1px solid rgba(255,255,255,0.08);
                                padding-bottom:9px;margin-bottom:8px;">
                      {img}
                      <div style="flex:1;">
                        <div style="color:#fff;font-weight:800;font-size:17px;">{row['name']}</div>
                        <div style="color:#8896a8;font-size:10px;">#{num} · G · {row['team']}</div>
                      </div>
                      <div style="text-align:right;">
                        <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;">{_z_str(row['z'])}</div>
                        <div style="color:#8896a8;font-size:9px;">Sv% form</div>
                      </div>
                    </div>""")

                sv   = float(row["sv_pct"]) if pd.notna(row["sv_pct"]) else 0
                sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else "#8896a8")
                gaa  = float(row["gaa"])  if pd.notna(row["gaa"])  else 0
                gaa_c= "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")
                gc   = st.columns(6)
                for i,(lbl,val,col) in enumerate([
                    ("GP",    int(row["gp"]),     "#fff"),
                    ("W",     int(row["w"]) if pd.notna(row["w"]) else "—", "#5a8f4e"),
                    ("Sv%",   f"{sv:.2f}%",       sv_c),
                    ("GAA",   f"{gaa:.2f}",        gaa_c),
                    ("SO",    int(row["so"]) if pd.notna(row["so"]) else 0, "#8896a8"),
                    ("Sv%/5g",f"{float(row['sv5']):.2f}%", "#f97316"),
                ]):
                    with gc[i]:
                        st.html(_stat_block(lbl, val, col, 15))

                if tab == "Overview":
                    df_gg = _goalie_games(int(sel_id))
                    if not df_gg.empty:
                        # Sv% trend chart
                        fig_sv = go.Figure()
                        sv_colors = [
                            "#f97316" if v >= 93 else ("#5a8f4e" if v >= 91 else ("#8896a8" if v >= 89 else "#87ceeb"))
                            for v in df_gg["sv_pct"]
                        ]
                        fig_sv.add_bar(
                            x=df_gg["date"].astype(str).str[:10], y=df_gg["sv_pct"],
                            marker_color=sv_colors, name="Sv%",
                            hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
                        )
                        fig_sv.add_hline(y=91.5, line_dash="dot", line_color="#f97316",
                                         annotation_text="elite 91.5%", annotation_font_size=8,
                                         annotation_font_color="#f97316")
                        layout_sv = dict(**CHART_BASE)
                        layout_sv["height"] = 200
                        layout_sv["yaxis"] = dict(gridcolor="rgba(255,255,255,0.04)",
                                                   tickfont=dict(size=9), range=[85, 100])
                        fig_sv.update_layout(**layout_sv)
                        fig_sv.update_xaxes(tickangle=45, nticks=12)
                        st.plotly_chart(fig_sv, use_container_width=True,
                                        config={"displayModeBar": False})

                        _panel_header("Last 12 games")
                        rows_html = ""
                        for _, g in df_gg.iterrows():
                            sv_val = float(g["sv_pct"])
                            sv_col = "#f97316" if sv_val >= 93 else ("#5a8f4e" if sv_val >= 91 else ("#8896a8" if sv_val >= 89 else "#87ceeb"))
                            ha_str = "vs" if g.get("is_home") else "@"
                            rows_html += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;font-family:monospace;">{str(g["date"])[:10]}</td>'
                                f'<td style="padding:4px 6px;color:#8896a8;font-size:10px;">{ha_str}</td>'
                                f'<td style="padding:4px 6px;color:#8896a8;font-size:10px;text-align:center;">{int(g["SA"])}</td>'
                                f'<td style="padding:4px 6px;color:#fff;font-size:10px;text-align:center;">{int(g["SV"])}</td>'
                                f'<td style="padding:4px 6px;color:{sv_col};font-family:monospace;font-size:11px;text-align:center;">{sv_val:.2f}%</td>'
                                f'<td style="padding:4px 6px;color:#c41e3a;font-size:10px;text-align:center;">{int(g["GA"])}</td>'
                                f'<td style="padding:4px 10px;color:#8896a8;font-size:10px;text-align:right;">{int(g["TOI"])}</td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:left;">Date</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;">H/A</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:center;">SA</th>'
                            f'<th style="padding:4px 6px;color:#8896a8;font-size:9px;text-align:center;">SV</th>'
                            f'<th style="padding:4px 6px;color:#f97316;font-size:9px;text-align:center;">Sv%</th>'
                            f'<th style="padding:4px 6px;color:#c41e3a;font-size:9px;text-align:center;">GA</th>'
                            f'<th style="padding:4px 10px;color:#8896a8;font-size:9px;text-align:right;">Min</th>'
                            f'</tr></thead><tbody>{rows_html}</tbody></table>'
                        )

                elif tab == "Career":
                    st.page_link("pages/11_Goalies.py", label="→ Full Goalie profile with career arc",
                                 icon=":material/sports:")

                elif tab == "Splits":
                    df_gs = _goalie_splits(int(sel_id))
                    _panel_header("Home vs Away — current season")
                    if df_gs.empty:
                        st.markdown("<p style='color:#8896a8;font-size:11px;'>No split data.</p>",
                                    unsafe_allow_html=True)
                    else:
                        hg = df_gs[df_gs["is_home"] == True]
                        ag = df_gs[df_gs["is_home"] == False]
                        hr = hg.iloc[0] if not hg.empty else None
                        ar = ag.iloc[0] if not ag.empty else None
                        def _gv(r, col, fmt=None):
                            if r is None or pd.isna(r[col]): return "—"
                            v = r[col]; return fmt(v) if fmt else str(int(v))
                        _ha_compare_table([
                            ("GP",  _gv(hr,"gp"),                          _gv(ar,"gp"),                          "#8896a8"),
                            ("Sv%", _gv(hr,"sv_pct",lambda v:f"{v:.2f}%"), _gv(ar,"sv_pct",lambda v:f"{v:.2f}%"),"#f97316"),
                            ("GAA", _gv(hr,"gaa",lambda v:f"{v:.2f}"),     _gv(ar,"gaa",lambda v:f"{v:.2f}"),    "#5a8f4e"),
                            ("GA",  _gv(hr,"ga"),                           _gv(ar,"ga"),                          "#c41e3a"),
                            ("SA",  _gv(hr,"sa"),                           _gv(ar,"sa"),                          "#8896a8"),
                        ])

        # ══════════════════════════════════════════════════════════════════════
        #  TEAM CENTER
        # ══════════════════════════════════════════════════════════════════════
        else:
            row = df_src[df_src["abbr"] == sel_id]
            if row.empty:
                st.info("Team not in current filter.")
            else:
                row  = row.iloc[0]
                zc   = _z_color(row["z"])
                diff = int(row["diff"]) if pd.notna(row["diff"]) else 0
                diff_c = "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")
                _div_labels = {"A":"Atlantic","M":"Metropolitan","C":"Central","P":"Pacific"}
                div_label  = _div_labels.get(row["div"], row["div"])
                conf_label = "Eastern" if row["conf"] == "E" else "Western"

                st.html(f"""
                <div style="display:flex;align-items:center;gap:16px;
                            border-bottom:1px solid rgba(255,255,255,0.08);
                            padding-bottom:9px;margin-bottom:8px;">
                  <div style="font-weight:900;font-size:34px;color:#fff;
                              font-family:monospace;letter-spacing:-0.02em;">{row['abbr']}</div>
                  <div style="flex:1;">
                    <div style="color:#8896a8;font-size:10px;">
                      {div_label} Division · {conf_label} Conference
                    </div>
                  </div>
                  <div style="text-align:right;">
                    <div style="color:{zc};font-weight:900;font-size:22px;font-family:monospace;">{_z_str(row['z'])}</div>
                    <div style="color:#8896a8;font-size:9px;">form σ</div>
                  </div>
                </div>""")

                pp  = float(row["pp_pct"]) if pd.notna(row["pp_pct"]) else 0
                pk  = float(row["pk_pct"]) if pd.notna(row["pk_pct"]) else 0
                tc_ = st.columns(8)
                for i,(lbl,val,col) in enumerate([
                    ("GP",  int(row["gp"]),  "#8896a8"),
                    ("W",   int(row["w"]),   "#5a8f4e"),
                    ("L",   int(row["l"]),   "#c41e3a"),
                    ("OTL", int(row["otl"]), "#8896a8"),
                    ("PTS", int(row["pts"]), "#5a8f4e"),
                    ("DIFF",(f"+{diff}" if diff>0 else str(diff)), diff_c),
                    ("PP%", f"{pp:.1f}%",   "#f97316" if pp>=25 else "#8896a8"),
                    ("PK%", f"{pk:.1f}%",   "#87ceeb" if pk>=83 else "#8896a8"),
                ]):
                    with tc_[i]:
                        st.html(_stat_block(lbl, val, col, 15))

                if tab == "Overview":
                    df_tg = _team_games(sel_id)
                    if not df_tg.empty:
                        # GF/GA chart
                        fig_team = go.Figure()
                        result_colors = [
                            "#5a8f4e" if r == "W" else ("#87ceeb" if r == "OTL" else "#c41e3a")
                            for r in df_tg["result"]
                        ]
                        fig_team.add_bar(
                            x=df_tg["date"].astype(str).str[:10],
                            y=df_tg["GF"].fillna(0),
                            marker_color=result_colors,
                            name="GF",
                            hovertemplate="%{x}: %{y} GF<extra></extra>",
                        )
                        fig_team.add_scatter(
                            x=df_tg["date"].astype(str).str[:10],
                            y=df_tg["GA"].fillna(0),
                            mode="lines+markers",
                            line=dict(color="#c41e3a", width=1.5, dash="dot"),
                            marker=dict(size=4),
                            name="GA",
                            hovertemplate="%{x}: %{y} GA<extra></extra>",
                        )
                        layout_team = dict(**CHART_BASE)
                        layout_team["height"] = 210
                        layout_team["legend"] = dict(orientation="h", y=1.08, font=dict(size=9))
                        fig_team.update_layout(**layout_team)
                        fig_team.update_xaxes(tickangle=45, nticks=12)
                        st.plotly_chart(fig_team, use_container_width=True,
                                        config={"displayModeBar": False})

                        _panel_header("Last 12 games")
                        rows_html = ""
                        for _, g in df_tg.iterrows():
                            res   = str(g["result"])
                            res_c = "#5a8f4e" if res=="W" else ("#87ceeb" if res=="OTL" else "#c41e3a")
                            gf, ga = g["GF"], g["GA"]
                            score_c = "#5a8f4e" if (pd.notna(gf) and pd.notna(ga) and gf>ga) else "#c41e3a"
                            score   = f'{int(gf)}–{int(ga)}' if pd.notna(gf) else "—"
                            rows_html += (
                                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
                                f'<td style="padding:3px 8px;color:#8896a8;font-size:10px;font-family:monospace;">{str(g["date"])[:10]}</td>'
                                f'<td style="padding:3px 6px;color:#8896a8;font-size:10px;">{g["ha"]}</td>'
                                f'<td style="padding:3px 6px;color:#fff;font-weight:600;font-size:11px;font-family:monospace;">{g["opp"]}</td>'
                                f'<td style="padding:3px 6px;color:{score_c};font-family:monospace;font-size:11px;text-align:center;">{score}</td>'
                                f'<td style="padding:3px 8px;text-align:center;">'
                                f'<span style="color:{res_c};background:{res_c}22;padding:1px 6px;'
                                f'border-radius:3px;font-size:10px;font-weight:700;">{res}</span></td>'
                                f'</tr>'
                            )
                        st.html(
                            f'<table style="width:100%;border-collapse:collapse;">'
                            f'<thead><tr style="background:rgba(255,255,255,0.03);">'
                            f'<th style="padding:3px 8px;color:#8896a8;font-size:9px;text-align:left;">Date</th>'
                            f'<th style="padding:3px 6px;color:#8896a8;font-size:9px;">H/A</th>'
                            f'<th style="padding:3px 6px;color:#8896a8;font-size:9px;">Opp</th>'
                            f'<th style="padding:3px 6px;color:#8896a8;font-size:9px;text-align:center;">Score</th>'
                            f'<th style="padding:3px 8px;color:#8896a8;font-size:9px;text-align:center;">Result</th>'
                            f'</tr></thead><tbody>{rows_html}</tbody></table>'
                        )

                elif tab == "Career":
                    st.page_link("pages/9_Team_History.py",
                                 label="→ Full Team History with franchise arc",
                                 icon=":material/history:")

                elif tab == "Splits":
                    df_ts = _team_splits(sel_id)
                    _panel_header("Home vs Away — current season")
                    if df_ts.empty:
                        st.markdown("<p style='color:#8896a8;font-size:11px;'>No split data.</p>",
                                    unsafe_allow_html=True)
                    else:
                        ht = df_ts[df_ts["is_home"] == True]
                        at = df_ts[df_ts["is_home"] == False]
                        hr = ht.iloc[0] if not ht.empty else None
                        ar = at.iloc[0] if not at.empty else None
                        def _tv(r, col, fmt=None):
                            if r is None or pd.isna(r[col]): return "—"
                            v = r[col]; return fmt(v) if fmt else str(int(v))
                        _ha_compare_table([
                            ("GP",   _tv(hr,"gp"),                           _tv(ar,"gp"),                           "#8896a8"),
                            ("W",    _tv(hr,"w"),                            _tv(ar,"w"),                            "#5a8f4e"),
                            ("OTL",  _tv(hr,"otl"),                          _tv(ar,"otl"),                          "#87ceeb"),
                            ("L",    _tv(hr,"l"),                            _tv(ar,"l"),                            "#c41e3a"),
                            ("PTS",  _tv(hr,"pts"),                          _tv(ar,"pts"),                          "#5a8f4e"),
                            ("GF/g", _tv(hr,"gf_avg",lambda v:f"{v:.2f}"),  _tv(ar,"gf_avg",lambda v:f"{v:.2f}"),  "#f97316"),
                            ("GA/g", _tv(hr,"ga_avg",lambda v:f"{v:.2f}"),  _tv(ar,"ga_avg",lambda v:f"{v:.2f}"),  "#c41e3a"),
                        ])

# ─────────────────────────────────────────────────────────────────────────────
#  RIGHT PANEL — persistent bio card
# ─────────────────────────────────────────────────────────────────────────────
with col_right:
    sel_id = st.session_state.t_id
    if sel_id is None:
        st.markdown(
            "<p style='color:rgba(255,255,255,0.15);font-size:11px;margin-top:40px;text-align:center;'>—</p>",
            unsafe_allow_html=True,
        )
    else:
        if mode == "Players" and not is_goalie_mode:
            row = df_src[df_src["pid"] == sel_id]
            if not row.empty:
                row  = row.iloc[0]
                zc   = _z_color(row["z"])
                bio  = _player_bio(int(sel_id))
                hs   = str(bio["headshot"]) if (bio is not None and bio["headshot"]) else ""
                img  = _headshot_html(hs, row["name"], zc, 52)
                pm   = row["pm"]
                pm_s = (f"+{int(pm)}" if pm > 0 else str(int(pm))) if pd.notna(pm) else "—"
                pm_c = "#5a8f4e" if (pd.notna(pm) and pm > 0) else ("#c41e3a" if (pd.notna(pm) and pm < 0) else "#8896a8")
                ppp  = int(row["ppp"]) if pd.notna(row["ppp"]) else "—"

                # Bio meta from players table
                if bio is not None:
                    birth    = str(bio["birthDate"])[:10] if bio["birthDate"] else "—"
                    nat      = str(bio["birthCountry"]) if bio["birthCountry"] else "—"
                    h_cm     = int(bio["heightInCentimeters"]) if bio["heightInCentimeters"] else 0
                    w_kg     = int(bio["weightInKilograms"])   if bio["weightInKilograms"]   else 0
                    feet, inch = divmod(round(h_cm/2.54), 12)
                    lbs      = round(w_kg*2.205)
                    num      = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    meta_rows = f"""
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Team</span>
                      <span style="color:#fff;font-size:10px;font-weight:600;">{row['team']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Position</span>
                      <span style="color:#fff;font-size:10px;">{row['pos']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Sweater</span>
                      <span style="color:#fff;font-size:10px;">#{num}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Born</span>
                      <span style="color:#fff;font-size:10px;">{birth}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Country</span>
                      <span style="color:#fff;font-size:10px;">{nat}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;
                                border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Height</span>
                      <span style="color:#fff;font-size:10px;">{feet}'{inch}" / {h_cm}cm</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;">
                      <span style="color:#8896a8;font-size:10px;">Weight</span>
                      <span style="color:#fff;font-size:10px;">{lbs} lbs / {w_kg}kg</span>
                    </div>"""
                else:
                    meta_rows = ""

                insight = _ai_insight(row["name"], row["team"])
                thesis_text, thesis_color = _quick_thesis(float(row["z"]), int(row["gp"]))

                # Traffic light signals
                _tl_form   = "#5a8f4e" if float(row["z"]) >= 0.8 else ("#8896a8" if float(row["z"]) > -0.8 else "#87ceeb")
                _tl_toi    = ("#5a8f4e" if (pd.notna(row["toi"]) and float(row["toi"]) >= 18)
                               else ("#f97316" if (pd.notna(row["toi"]) and float(row["toi"]) >= 14)
                               else "#8896a8"))
                _sh_f      = float(row["sh_pct"]) if pd.notna(row["sh_pct"]) else None
                _tl_sh     = ("#f97316" if (_sh_f is not None and _sh_f >= 16)
                               else ("#5a8f4e" if (_sh_f is not None and _sh_f >= 8)
                               else "#8896a8"))
                _tl_sample = "#5a8f4e" if int(row["gp"]) >= 30 else ("#f97316" if int(row["gp"]) >= 15 else "#c41e3a")
                _tl_sh_warn = f" ⚠ {_sh_f:.0f}%" if (_sh_f is not None and _sh_f >= 16) else ""
                _traffic_html = (
                    f'<div style="display:grid;grid-template-columns:14px 1fr 14px 1fr;'
                    f'gap:3px 6px;margin-bottom:8px;align-items:center;">'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{_tl_form};display:inline-block;"></span>'
                    f'<span style="color:#8896a8;font-size:9px;">Form</span>'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{_tl_toi};display:inline-block;"></span>'
                    f'<span style="color:#8896a8;font-size:9px;">Ice time</span>'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{_tl_sh};display:inline-block;"></span>'
                    f'<span style="color:#8896a8;font-size:9px;">SH%{_tl_sh_warn}</span>'
                    f'<span style="width:8px;height:8px;border-radius:50%;background:{_tl_sample};display:inline-block;"></span>'
                    f'<span style="color:#8896a8;font-size:9px;">Sample</span>'
                    f'</div>'
                )

                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    {img}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:12px;line-height:1.3;">{row['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">{row['pos']} · {row['team']}</div>
                    </div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:20px;font-family:monospace;
                              text-align:center;padding:6px 0 4px;
                              border-bottom:1px solid rgba(255,255,255,0.07);
                              margin-bottom:6px;">{_z_str(row['z'])}</div>
                  <div style="background:{thesis_color}14;border:1px solid {thesis_color}33;
                              border-radius:4px;padding:5px 8px;margin-bottom:8px;text-align:center;">
                    <span style="color:{thesis_color};font-size:10px;font-weight:600;">{thesis_text}</span>
                  </div>
                  {_traffic_html}
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:10px;">
                    {_stat_block('PTS',  int(row['pts']),                  '#5a8f4e', 15)}
                    {_stat_block('+/-',  pm_s,                             pm_c,      15)}
                    {_stat_block('G',    int(row['g']),                    '#fff',    15)}
                    {_stat_block('A',    int(row['a']),                    '#8896a8', 15)}
                    {_stat_block('PPP',  ppp,                              '#87ceeb', 15)}
                    {_stat_block('5g',   f"{row['avg5']:.2f}",             '#f97316', 15)}
                  </div>
                  <div style="margin-bottom:10px;">{meta_rows}</div>
                  {f'<div style="background:rgba(255,255,255,0.02);border-radius:4px;padding:6px 8px;margin-bottom:8px;"><div style="color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:2px;">AI Insight</div><div style="color:#8896a8;font-size:10px;line-height:1.5;">{insight}</div></div>' if insight else ''}
                  <a href="/Player_History" target="_self"
                     style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                    Full career profile →</a>
                </div>""")

                # Watchlist button
                from lib import userdb as _udb
                from lib.auth import get_user as _get_user
                _uid = (_get_user() or {}).get("id", "")
                _watched_ids = _udb.watchlist_ids(_uid)
                _is_watched  = sel_id in _watched_ids
                if _is_watched:
                    if st.button("✓ Watching", key=f"rp_watch_{sel_id}",
                                 use_container_width=True, type="secondary"):
                        _udb.watchlist_remove(sel_id, _uid)
                        st.rerun()
                elif not has_feature("watchlist"):
                    soft_gate("watchlist", "Watchlist",
                              "Spåra dina favoritspelare med Base-plan.")
                elif watchlist_slots_remaining(_uid) <= 0:
                    soft_gate("watchlist_unlimited", "Fler watchlist-platser",
                              "Base ger 10 platser — Plus ger obegränsat.")
                else:
                    if st.button("+ Watch player", key=f"rp_watch_{sel_id}",
                                 use_container_width=True, type="primary"):
                        _udb.watchlist_add(sel_id, row["name"], row["team"], row["pos"], _uid)
                        st.rerun()

        elif mode == "Players" and is_goalie_mode:
            row = df_src[df_src["pid"] == sel_id]
            if not row.empty:
                row  = row.iloc[0]
                zc   = _z_color(row["z"])
                bio  = _player_bio(int(sel_id))
                hs   = str(bio["headshot"]) if (bio is not None and bio["headshot"]) else ""
                img  = _headshot_html(hs, row["name"], zc, 52)
                sv   = float(row["sv_pct"]) if pd.notna(row["sv_pct"]) else 0
                sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else "#8896a8")
                gaa  = float(row["gaa"])  if pd.notna(row["gaa"])  else 0
                gaa_c= "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")

                if bio is not None:
                    birth = str(bio["birthDate"])[:10] if bio["birthDate"] else "—"
                    nat   = str(bio["birthCountry"]) if bio["birthCountry"] else "—"
                    num   = int(bio["sweaterNumber"]) if bio["sweaterNumber"] else 0
                    meta_g = f"""
                    <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Team</span><span style="color:#fff;font-size:10px;font-weight:600;">{row['team']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Sweater</span><span style="color:#fff;font-size:10px;">#{num}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Born</span><span style="color:#fff;font-size:10px;">{birth}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;">
                      <span style="color:#8896a8;font-size:10px;">Country</span><span style="color:#fff;font-size:10px;">{nat}</span>
                    </div>"""
                else:
                    meta_g = ""

                g_thesis_text, g_thesis_color = _quick_thesis(float(row["z"]), int(row["gp"]))
                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    {img}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:12px;">{row['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">G · {row['team']}</div>
                    </div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:20px;font-family:monospace;
                              text-align:center;padding:6px 0 4px;
                              border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:6px;">{_z_str(row['z'])}</div>
                  <div style="background:{g_thesis_color}14;border:1px solid {g_thesis_color}33;
                              border-radius:4px;padding:5px 8px;margin-bottom:8px;text-align:center;">
                    <span style="color:{g_thesis_color};font-size:10px;font-weight:600;">{g_thesis_text}</span>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:10px;">
                    {_stat_block('Sv%',   f'{sv:.2f}%',                               sv_c,   14)}
                    {_stat_block('GAA',   f'{gaa:.2f}',                               gaa_c,  14)}
                    {_stat_block('W',     int(row['w']) if pd.notna(row['w']) else '—','#5a8f4e',14)}
                    {_stat_block('GP',    int(row['gp']),                             '#8896a8',14)}
                    {_stat_block('Sv%/5g',f'{float(row["sv5"]):.2f}%',               '#f97316',13)}
                    {_stat_block('SO',    int(row['so']) if pd.notna(row['so']) else 0,'#8896a8',14)}
                  </div>
                  <div style="margin-bottom:10px;">{meta_g}</div>
                  <a href="/Goalies" target="_self"
                     style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                    Full goalie profile →</a>
                </div>""")

        else:  # Teams right card
            row = df_src[df_src["abbr"] == sel_id]
            if not row.empty:
                row   = row.iloc[0]
                zc    = _z_color(row["z"])
                diff  = int(row["diff"]) if pd.notna(row["diff"]) else 0
                diff_c= "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")
                pp    = float(row["pp_pct"]) if pd.notna(row["pp_pct"]) else 0
                pk    = float(row["pk_pct"]) if pd.notna(row["pk_pct"]) else 0
                _dm   = {"A":"Atlantic","M":"Metropolitan","C":"Central","P":"Pacific"}
                insight = _ai_insight("", row["abbr"])

                st.html(f"""
                <div style="border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:12px;">
                  <div style="margin-bottom:10px;">
                    <div style="color:#fff;font-weight:900;font-size:26px;font-family:monospace;">{row['abbr']}</div>
                    <div style="color:#8896a8;font-size:10px;">{_dm.get(row['div'],'—')} Division</div>
                  </div>
                  <div style="color:{zc};font-weight:900;font-size:20px;font-family:monospace;
                              text-align:center;padding:6px 0 8px;
                              border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:8px;">{_z_str(row['z'])}</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:10px;">
                    {_stat_block('PTS',  int(row['pts']),                                '#5a8f4e',15)}
                    {_stat_block('W–L',  f"{int(row['w'])}–{int(row['l'])}",            '#fff',   13)}
                    {_stat_block('DIFF', (f"+{diff}" if diff>0 else str(diff)),           diff_c,  15)}
                    {_stat_block('PP%',  f'{pp:.1f}%', '#f97316' if pp>=25 else '#8896a8',14)}
                    {_stat_block('PK%',  f'{pk:.1f}%', '#87ceeb' if pk>=83 else '#8896a8',14)}
                    {_stat_block('SF/g', f'{float(row["sf"]):.1f}' if pd.notna(row["sf"]) else '—','#8896a8',14)}
                  </div>
                  <div style="margin-bottom:6px;">
                    <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">Conference</span>
                      <span style="color:#fff;font-size:10px;">{'Eastern' if row['conf']=='E' else 'Western'}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                      <span style="color:#8896a8;font-size:10px;">GF 10g avg</span>
                      <span style="color:#5a8f4e;font-size:10px;font-weight:600;">{f"{float(row['gf10']):.2f}" if pd.notna(row['gf10']) else '—'}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:3px 0;">
                      <span style="color:#8896a8;font-size:10px;">GA 10g avg</span>
                      <span style="color:#c41e3a;font-size:10px;font-weight:600;">{f"{float(row['ga10']):.2f}" if pd.notna(row['ga10']) else '—'}</span>
                    </div>
                  </div>
                  {f'<div style="background:rgba(255,255,255,0.02);border-radius:4px;padding:6px 8px;margin-bottom:8px;"><div style="color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:2px;">AI Insight</div><div style="color:#8896a8;font-size:10px;line-height:1.5;">{insight}</div></div>' if insight else ''}
                  <a href="/Teams" target="_self"
                     style="color:#5a8f4e;font-size:10px;text-decoration:underline;text-underline-offset:3px;">
                    Team dashboard →</a>
                </div>""")

# ── Legend ─────────────────────────────────────────────────────────────────────
st.markdown(
    """<div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;padding-top:8px;
                  border-top:1px solid rgba(255,255,255,0.06);">
      <span style="color:#f97316;font-size:9px;">■ Hot σ ≥ 1.5</span>
      <span style="color:#5a8f4e;font-size:9px;">■ Above avg σ ≥ 0.5</span>
      <span style="color:#8896a8;font-size:9px;">■ Neutral</span>
      <span style="color:#87ceeb;font-size:9px;">■ Below avg σ ≤ −0.5</span>
      <span style="color:#3b82f6;font-size:9px;">■ Cold σ ≤ −1.5</span>
      <span style="color:rgba(255,255,255,0.2);font-size:9px;margin-left:6px;">
        σ = z-score vs 20g baseline · click row to select</span>
    </div>""",
    unsafe_allow_html=True,
)
