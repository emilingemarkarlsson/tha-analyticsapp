"""Player Screener – filter and rank players like a stock screener."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, zscore_legend, data_source_footer, tier_badge_html
from lib import userdb

st.set_page_config(page_title="Player Finder – THA Analytics", page_icon="tha_icon.png", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

page_header("Player Finder", "Filter and rank players across any criteria", data_date=get_data_date())
zscore_legend()

# ── Presets ────────────────────────────────────────────────────────────────────
PRESETS = {
    "Hot Streak":      dict(pos=["C","L","R","D"], min_gp=20, z_min=0.8,  z_max=3.0, min_toi=10.0, min_pts5=0.0, sort="pts_zscore_5v20"),
    "Breakout":        dict(pos=["C","L","R"],      min_gp=10, z_min=0.5,  z_max=3.0, min_toi=8.0,  min_pts5=0.5, sort="pts_avg_5g"),
    "Cold Spell":      dict(pos=["C","L","R","D"], min_gp=20, z_min=-3.0, z_max=-0.8,min_toi=10.0, min_pts5=0.0, sort="pts_zscore_5v20"),
    "Point Per Game":  dict(pos=["C","L","R"],      min_gp=20, z_min=-3.0, z_max=3.0, min_toi=8.0,  min_pts5=1.0, sort="pts_avg_5g"),
    "Shutdown D":      dict(pos=["D"],              min_gp=20, z_min=-3.0, z_max=3.0, min_toi=18.0, min_pts5=0.0, sort="toi_avg_10g"),
    "Reset":           None,
}

preset_cols = st.columns(len(PRESETS))
active_preset = st.session_state.get("screener_preset")
for i, (label, config) in enumerate(PRESETS.items()):
    with preset_cols[i]:
        if st.button(label, key=f"preset_{label}", use_container_width=True):
            if label == "Reset":
                st.session_state.pop("screener_preset", None)
                st.session_state["filter_pos"]  = ["C","L","R","D"]
                st.session_state["filter_gp"]   = 10
                st.session_state["filter_z"]    = (-3.0, 3.0)
                st.session_state["filter_toi"]  = 0.0
                st.session_state["filter_pts5"] = 0.0
                st.session_state["filter_sort"] = "pts_zscore_5v20"
            else:
                st.session_state["screener_preset"] = label
                st.session_state["filter_pos"]  = config["pos"]
                st.session_state["filter_gp"]   = config["min_gp"]
                st.session_state["filter_z"]    = (config["z_min"], config["z_max"])
                st.session_state["filter_toi"]  = config["min_toi"]
                st.session_state["filter_pts5"] = config["min_pts5"]
                st.session_state["filter_sort"] = config["sort"]
            st.rerun()

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    fc1, fc2, fc3 = st.columns(3)

    SORT_OPTIONS = {
        "pts_zscore_5v20":   "Momentum",
        "pts_avg_5g":        "PTS / 5g",
        "pts_avg_20g":       "PTS / 20g",
        "pts_season":        "PTS season",
        "goals_season":      "Goals season",
        "toi_avg_10g":       "Ice Time / game",
        "goals_zscore_5v20": "Goals momentum",
    }

    with fc1:
        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;'>Position</p>", unsafe_allow_html=True)
        sel_pos = st.multiselect(
            "", ["C", "L", "R", "D"],
            default=["C","L","R","D"],
            label_visibility="collapsed", key="filter_pos",
        )

        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin:12px 0 4px;'>Min games played</p>", unsafe_allow_html=True)
        min_gp = st.slider("", 1, 77, 10, label_visibility="collapsed", key="filter_gp")

    with fc2:
        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;'>Momentum (5g vs 20g baseline)</p>", unsafe_allow_html=True)
        z_range = st.slider("", -3.0, 3.0, (-3.0, 3.0),
                            step=0.1, label_visibility="collapsed", key="filter_z")

        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin:12px 0 4px;'>Min ice time / game (min)</p>", unsafe_allow_html=True)
        min_toi = st.slider("", 0.0, 28.0, 0.0,
                            step=0.5, label_visibility="collapsed", key="filter_toi")

    with fc3:
        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;'>Min PTS / last 5 games</p>", unsafe_allow_html=True)
        min_pts5 = st.slider("", 0.0, 2.5, 0.0,
                             step=0.1, label_visibility="collapsed", key="filter_pts5")

        st.markdown("<p style='color:#8896a8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin:12px 0 4px;'>Sort by</p>", unsafe_allow_html=True)
        sort_keys = list(SORT_OPTIONS.keys())
        sort_col = st.selectbox(
            "", sort_keys,
            format_func=lambda x: SORT_OPTIONS[x],
            label_visibility="collapsed", key="filter_sort",
        )

# ── Query ──────────────────────────────────────────────────────────────────────
# Read current widget values from session state
sel_pos  = st.session_state.get("filter_pos",  ["C","L","R","D"])
min_gp   = st.session_state.get("filter_gp",   10)
z_range  = st.session_state.get("filter_z",    (-3.0, 3.0))
min_toi  = st.session_state.get("filter_toi",  0.0)
min_pts5 = st.session_state.get("filter_pts5", 0.0)
sort_col = st.session_state.get("filter_sort", "pts_zscore_5v20")

pos_list = "','".join(sel_pos) if sel_pos else "'C'"
toi_seconds = min_toi * 60

try:
    df = query(f"""
        SELECT
            CAST(player_id AS VARCHAR) AS player_id,
            player_first_name || ' ' || player_last_name AS name,
            team_abbr, position,
            gp_season, goals_season, assists_season, pts_season,
            ROUND(pts_avg_5g, 2)       AS pts_avg_5g,
            ROUND(pts_avg_20g, 2)      AS pts_avg_20g,
            ROUND(toi_avg_10g / 60, 1) AS toi_min,
            ROUND(pts_zscore_5v20, 2)  AS pts_zscore_5v20,
            ROUND(goals_zscore_5v20, 2) AS goals_zscore_5v20
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND player_first_name IS NOT NULL
          AND position IN ('{pos_list}')
          AND gp_season >= {min_gp}
          AND pts_zscore_5v20 BETWEEN {z_range[0]} AND {z_range[1]}
          AND toi_avg_10g >= {toi_seconds}
          AND pts_avg_5g >= {min_pts5}
        ORDER BY {sort_col} DESC
        LIMIT 500
    """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# ── Results ────────────────────────────────────────────────────────────────────
count = len(df)
sort_label = SORT_OPTIONS.get(sort_col, sort_col)
st.markdown(
    f"<p style='color:#8896a8;font-size:12px;margin-bottom:10px;'>"
    f"<span style='color:#fff;font-weight:700;'>{count}</span> players matched · sorted by <span style='color:#5a8f4e;font-weight:600;'>{sort_label}</span></p>",
    unsafe_allow_html=True,
)

if df.empty:
    st.info("No players match the current filters. Try widening the criteria.")
    st.stop()

# Build HTML table
rows_html = ""
for rank, (_, r) in enumerate(df.iterrows(), 1):
    bg = "rgba(255,255,255,0.02)" if rank % 2 == 0 else "transparent"
    rows_html += (
        f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);background:{bg};">'
        f'<td style="padding:7px 10px;color:rgba(255,255,255,0.25);font-size:11px;text-align:right;">{rank}</td>'
        f'<td style="padding:7px 14px;color:#fff;font-weight:600;font-size:13px;white-space:nowrap;">{r["name"]}</td>'
        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;">{r["team_abbr"]}</td>'
        f'<td style="padding:7px 8px;color:#8896a8;font-size:11px;text-align:center;">{r["position"]}</td>'
        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{int(r["gp_season"])}</td>'
        f'<td style="padding:7px 8px;color:#fff;font-size:12px;text-align:center;">{int(r["goals_season"])}</td>'
        f'<td style="padding:7px 8px;color:#fff;font-size:12px;text-align:center;">{int(r["assists_season"])}</td>'
        f'<td style="padding:7px 8px;color:#5a8f4e;font-weight:700;font-size:12px;text-align:center;">{int(r["pts_season"])}</td>'
        f'<td style="padding:7px 8px;color:#fff;font-size:12px;text-align:center;">{r["pts_avg_5g"]}</td>'
        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{r["pts_avg_20g"]}</td>'
        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{r["toi_min"]}</td>'
        f'<td style="padding:7px 14px;text-align:center;">{tier_badge_html(float(r["pts_zscore_5v20"]))}</td>'
        f'</tr>'
    )

thead = (
    '<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
    '<th style="padding:7px 10px;color:#8896a8;font-size:10px;font-weight:600;text-align:right;">#</th>'
    '<th style="padding:7px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">PLAYER</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;">TEAM</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">POS</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">GP</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">G</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">A</th>'
    '<th style="padding:7px 8px;color:#5a8f4e;font-size:10px;font-weight:700;text-align:center;">PTS</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">PTS/5g</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">PTS/20g</th>'
    '<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">ICE TIME</th>'
    '<th style="padding:7px 14px;color:#5a8f4e;font-size:10px;font-weight:700;text-align:center;">MOMENTUM</th>'
    '</tr></thead>'
)

st.html(
    f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
    f'<table style="width:100%;border-collapse:collapse;">{thead}<tbody>{rows_html}</tbody></table>'
    f'</div>'
)

# ── Watchlist / Roster quick-add ───────────────────────────────────────────────
st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

watched = userdb.watchlist_ids()
player_options = {
    f"{r['name']} ({r['team_abbr']})": r
    for _, r in df.iterrows()
}

wa_col, rb_col = st.columns([1, 1], gap="large")

with wa_col:
    st.markdown(
        "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Add to Watchlist</p>",
        unsafe_allow_html=True,
    )
    to_watch = st.multiselect(
        "", list(player_options.keys()),
        placeholder="Select players...",
        label_visibility="collapsed", key="quick_watch",
    )
    if st.button("Watch selected", key="btn_watch", use_container_width=True):
        for label in to_watch:
            r = player_options[label]
            userdb.watchlist_add(str(r["player_id"]), r["name"], r["team_abbr"], r["position"])
        st.success(f"Added {len(to_watch)} player(s) to watchlist.")
        st.session_state.pop("quick_watch", None)
        st.rerun()

    already = [f"{r['name']} ({r['team_abbr']})" for _, r in df.iterrows() if str(r["player_id"]) in watched]
    if already:
        st.markdown(
            f"<p style='color:#5a8f4e;font-size:11px;margin-top:6px;'>"
            f"{len(already)} already watched: {', '.join(already[:5])}{'…' if len(already)>5 else ''}</p>",
            unsafe_allow_html=True,
        )

with rb_col:
    rosters = userdb.roster_list()
    st.markdown(
        "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Add to Roster</p>",
        unsafe_allow_html=True,
    )
    if not rosters:
        st.markdown(
            "<p style='color:#8896a8;font-size:12px;'>No rosters yet — create one on the Watchlist page.</p>",
            unsafe_allow_html=True,
        )
    else:
        roster_names = {r["name"]: r["roster_id"] for r in rosters}
        sel_roster = st.selectbox("", list(roster_names.keys()),
                                  label_visibility="collapsed", key="quick_roster_sel")
        to_add = st.multiselect(
            "", list(player_options.keys()),
            placeholder="Select players...",
            label_visibility="collapsed", key="quick_roster_players",
        )
        if st.button("Add to roster", key="btn_roster", use_container_width=True):
            rid = roster_names[sel_roster]
            for label in to_add:
                r = player_options[label]
                userdb.roster_add_player(rid, str(r["player_id"]), r["name"], r["team_abbr"], r["position"])
            st.success(f"Added {len(to_add)} player(s) to '{sel_roster}'.")
            st.session_state.pop("quick_roster_players", None)
            st.rerun()

data_source_footer('Screener uses player_rolling_stats WHERE game_recency_rank = 1 (latest snapshot per player)')
