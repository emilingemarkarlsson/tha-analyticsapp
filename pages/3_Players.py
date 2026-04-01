"""Players page – sortable form table."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, zscore_legend, data_source_footer, tier_badge_html

st.set_page_config(page_title="Players – THA Analytics", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

page_header("Players", "Current season form · 5-game vs 20-game baseline z-score", data_date=get_data_date())
zscore_legend()

try:
    df = query("""
        SELECT CAST(player_id AS VARCHAR) AS player_id,
               player_first_name || ' ' || player_last_name AS name,
               team_abbr, gp_season, goals_season, assists_season,
               pts_avg_5g, pts_avg_20g, pts_zscore_5v20
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND gp_season >= 10
        ORDER BY ABS(pts_zscore_5v20) DESC
        LIMIT 300
    """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

# Controls
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    search = st.text_input("", placeholder="Search player or team...", label_visibility="collapsed")
with c2:
    sort_col = st.selectbox(
        "",
        ["pts_zscore_5v20", "pts_avg_5g", "pts_avg_20g", "goals_season", "assists_season", "gp_season"],
        format_func=lambda x: {
            "pts_zscore_5v20": "Form (σ)",
            "pts_avg_5g": "PTS/5",
            "pts_avg_20g": "PTS/20",
            "goals_season": "Goals",
            "assists_season": "Assists",
            "gp_season": "GP",
        }.get(x, x),
        label_visibility="collapsed",
    )
with c3:
    asc = st.toggle("Ascending", value=False)

# Filter + sort
filtered = df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["name"].str.lower().str.contains(q) |
        filtered["team_abbr"].str.lower().str.contains(q)
    ]
filtered = filtered.sort_values(sort_col, ascending=asc).reset_index(drop=True)

st.markdown(
    f"<p style='color:#8896a8;font-size:11px;margin-bottom:8px;'>{len(filtered)} players</p>",
    unsafe_allow_html=True,
)

# Render table as HTML for colour-coded z-score
rows_html = ""
for idx, row in filtered.iterrows():
    z = float(row["pts_zscore_5v20"])
    rows_html += f"""
    <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
      <td style="padding:8px 14px;color:#fff;font-weight:500;font-size:12px;">{row['name']}</td>
      <td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{row['team_abbr']}</td>
      <td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{int(row['gp_season'])}</td>
      <td style="text-align:center;padding:8px 8px;color:#fff;font-size:12px;">{int(row['goals_season'])}</td>
      <td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{int(row['assists_season'])}</td>
      <td style="text-align:center;padding:8px 8px;color:#fff;font-weight:500;font-size:12px;">{float(row['pts_avg_5g']):.2f}</td>
      <td style="text-align:center;padding:8px 8px;color:#8896a8;font-size:12px;">{float(row['pts_avg_20g']):.2f}</td>
      <td style="text-align:center;padding:8px 8px;">{tier_badge_html(z)}</td>
    </tr>"""

st.markdown(
    f"""<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">
          <th style="text-align:left;padding:9px 14px;color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;white-space:nowrap;">Player</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">Team</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">GP</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">G</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">A</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">PTS/5</th>
          <th style="text-align:center;padding:9px 8px;color:#8896a8;font-size:10px;font-weight:600;">PTS/20</th>
          <th style="text-align:center;padding:9px 8px;color:#5a8f4e;font-size:10px;font-weight:700;">Form (σ)</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table></div>
    <div style="padding:8px 14px;color:#8896a8;font-size:11px;border-top:1px solid rgba(255,255,255,0.06);">
      {len(filtered)} players · Use the sort dropdown above to reorder
    </div></div>""",
    unsafe_allow_html=True,
)

data_source_footer('Form (σ) = z-score of last 5 games vs 20-game rolling average')
