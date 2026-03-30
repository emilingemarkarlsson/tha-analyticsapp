"""Standings page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query
from lib.sidebar import render as _render_sidebar

st.set_page_config(page_title="Standings – THA Analytics", layout="wide")
_render_sidebar()

st.markdown(
    "<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;margin-bottom:4px;'>Standings</h1>"
    "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>Current season · Regular season</p>",
    unsafe_allow_html=True,
)

DIVISION_ORDER = ["A", "M", "C", "P"]
DIVISION_NAMES = {"A": "Atlantic", "M": "Metropolitan", "C": "Central", "P": "Pacific"}
CONF_MAP = {"A": "E", "M": "E", "C": "W", "P": "W"}

try:
    df = query("""
        SELECT teamAbbrev, wins, losses, otLosses, points, gamesPlayed,
               goalFor, goalAgainst, divisionAbbrev, conferenceAbbrev,
               streakCode, streakCount
        FROM standings
        WHERE season = (SELECT MAX(season) FROM standings)
        ORDER BY divisionAbbrev, points DESC
        LIMIT 40
    """)
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()

df["DIFF"] = df["goalFor"].astype(int) - df["goalAgainst"].astype(int)
df["STREAK"] = df["streakCode"].astype(str) + df["streakCount"].astype(str)

# Build conference-wide WC tables
def get_playoff_status(row: pd.Series, df_all: pd.DataFrame) -> str:
    div = row["divisionAbbrev"]
    conf = CONF_MAP.get(div, "")
    div_idx = df_all[df_all["divisionAbbrev"] == div].index.get_loc(row.name)
    if div_idx < 3:
        return "DIV"
    conf_teams = (
        df_all[df_all["divisionAbbrev"].map(CONF_MAP) == conf]
        .sort_values("points", ascending=False)
    )
    div_tops = []
    for d, grp in df_all.groupby("divisionAbbrev"):
        if CONF_MAP.get(d) == conf:
            div_tops.extend(grp.sort_values("points", ascending=False).head(3)["teamAbbrev"].tolist())
    wc = conf_teams[~conf_teams["teamAbbrev"].isin(div_tops)].head(2)["teamAbbrev"].tolist()
    if row["teamAbbrev"] in wc:
        return "WC"
    return ""

df["status"] = df.apply(get_playoff_status, axis=1, df_all=df)

# Legend
st.markdown(
    """<div style="display:flex;gap:20px;margin-bottom:20px;font-size:12px;color:#8896a8;">
      <span>
        <span style="color:#5a8f4e;border:1px solid #5a8f4e;padding:1px 5px;border-radius:3px;
                     font-size:10px;font-weight:700;">DIV</span>
        &nbsp; Division leader (top 3)
      </span>
      <span>
        <span style="color:#87ceeb;border:1px solid #87ceeb;padding:1px 5px;border-radius:3px;
                     font-size:10px;font-weight:700;">WC</span>
        &nbsp; Wild card
      </span>
    </div>""",
    unsafe_allow_html=True,
)

def _division_html(div_df: pd.DataFrame, div: str, conf_label: str) -> str:
    """Build full HTML block for one division table."""
    rows_html = ""
    for idx, row in div_df.iterrows():
        status = row["status"]
        diff = int(row["DIFF"])
        diff_color = "#5a8f4e" if diff >= 0 else "#c41e3a"
        diff_str = f"+{diff}" if diff >= 0 else str(diff)
        badge = ""
        if status == "DIV":
            badge = "<span style='color:#5a8f4e;border:1px solid #5a8f4e;padding:0 4px;border-radius:2px;font-size:9px;font-weight:700;margin-right:4px;'>DIV</span>"
        elif status == "WC":
            badge = "<span style='color:#87ceeb;border:1px solid #87ceeb;padding:0 4px;border-radius:2px;font-size:9px;font-weight:700;margin-right:4px;'>WC</span>"
        bg = "rgba(255,255,255,0.02)" if idx % 2 == 0 else "transparent"
        rows_html += (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);background:{bg};">'
            f'<td style="padding:8px 14px;white-space:nowrap;">'
            f'<span style="color:rgba(255,255,255,0.2);font-size:11px;margin-right:4px;">{idx+1}</span>'
            f'{badge}'
            f'<span style="color:#fff;font-weight:600;font-size:12px;">{row["teamAbbrev"]}</span>'
            f'</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#8896a8;font-size:12px;">{int(row["gamesPlayed"])}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#fff;font-weight:600;font-size:12px;">{int(row["wins"])}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#8896a8;font-size:12px;">{int(row["losses"])}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#8896a8;font-size:12px;">{int(row["otLosses"])}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#5a8f4e;font-weight:700;font-size:12px;">{int(row["points"])}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:{diff_color};font-family:monospace;font-size:11px;">{diff_str}</td>'
            f'<td style="text-align:center;padding:8px 6px;color:#8896a8;font-family:monospace;font-size:11px;">{row["STREAK"]}</td>'
            f'</tr>'
        )
    return (
        f'<div style="margin-top:16px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:5px 5px 0 0;padding:10px 14px;">'
        f'<span style="color:#fff;font-weight:700;font-size:13px;">{DIVISION_NAMES[div]} Division</span>'
        f'<span style="color:#8896a8;font-size:11px;">{conf_label} Conference</span>'
        f'</div>'
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-top:none;border-radius:0 0 5px 5px;overflow:hidden;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'<th style="text-align:left;padding:7px 14px;color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Team</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">GP</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">W</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">L</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">OTL</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#5a8f4e;font-size:10px;font-weight:700;">PTS</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">DIFF</th>'
        f'<th style="text-align:center;padding:7px 6px;color:#8896a8;font-size:10px;font-weight:600;">STK</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div></div>'
    )


col1, col2 = st.columns(2, gap="large")

html_left, html_right = "", ""
for i, div in enumerate(DIVISION_ORDER):
    div_df = df[df["divisionAbbrev"] == div].reset_index(drop=True)
    if div_df.empty:
        continue
    conf_label = "Eastern" if CONF_MAP[div] == "E" else "Western"
    block = _division_html(div_df, div, conf_label)
    if i < 2:
        html_left += block
    else:
        html_right += block

with col1:
    st.html(html_left)
with col2:
    st.html(html_right)
