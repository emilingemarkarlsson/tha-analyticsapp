"""Standings page – supports all leagues."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query, get_data_date, get_standings
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, data_source_footer
from lib.entitlements import has_feature

st.set_page_config(page_title="Standings – THA Analytics", page_icon="tha_icon.png", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

page_header(
    "NHL Standings",
    "Current season · DIV = playoff spot, WC = wild card",
    data_date=get_data_date(),
)

# ══════════════════════════════════════════════════════════════════════════════
# NHL standings – full division/conference table
# ══════════════════════════════════════════════════════════════════════════════
if active_league == "nhl":
    DIVISION_ORDER = ["A", "M", "C", "P"]
    DIVISION_NAMES = {"A": "Atlantic", "M": "Metropolitan", "C": "Central", "P": "Pacific"}
    CONF_MAP = {"A": "E", "M": "E", "C": "W", "P": "W"}

    try:
        df = query("""
            SELECT st.teamAbbrev, st.wins, st.losses, st.otLosses, st.points, st.gamesPlayed,
                   st.goalFor, st.goalAgainst, st.divisionAbbrev, st.conferenceAbbrev,
                   st.streakCode, st.streakCount,
                   ts.powerPlayPct, ts.penaltyKillPct
            FROM standings st
            LEFT JOIN team_stats ts ON ts.teamFullName = st.teamName AND ts.season = st.season
            WHERE st.season = (SELECT MAX(season) FROM standings)
            ORDER BY st.divisionAbbrev, st.points DESC
            LIMIT 40
        """, league="nhl")
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()

    df["DIFF"] = df["goalFor"].astype(int) - df["goalAgainst"].astype(int)
    df["STREAK"] = df["streakCode"].astype(str) + df["streakCount"].astype(str)
    df["PP"] = (df["powerPlayPct"].fillna(0) * 100).round(1)
    df["PK"] = (df["penaltyKillPct"].fillna(0) * 100).round(1)

    def get_playoff_status(row: pd.Series, df_all: pd.DataFrame) -> str:
        div = row["divisionAbbrev"]
        conf = CONF_MAP.get(div, "")
        div_idx = df_all[df_all["divisionAbbrev"] == div].index.get_loc(row.name)
        if div_idx < 3:
            return "DIV"
        div_tops = []
        for d, grp in df_all.groupby("divisionAbbrev"):
            if CONF_MAP.get(d) == conf:
                div_tops.extend(grp.sort_values("points", ascending=False).head(3)["teamAbbrev"].tolist())
        conf_teams = (
            df_all[df_all["divisionAbbrev"].map(CONF_MAP) == conf]
            .sort_values("points", ascending=False)
        )
        wc = conf_teams[~conf_teams["teamAbbrev"].isin(div_tops)].head(2)["teamAbbrev"].tolist()
        return "WC" if row["teamAbbrev"] in wc else ""

    df["status"] = df.apply(get_playoff_status, axis=1, df_all=df)

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
            pp_val  = float(row["PP"]) if row["PP"] else 0.0
            pk_val  = float(row["PK"]) if row["PK"] else 0.0
            pp_color = "#f97316" if pp_val >= 25 else ("#5a8f4e" if pp_val >= 20 else "#8896a8")
            pk_color = "#f97316" if pk_val >= 83 else ("#5a8f4e" if pk_val >= 78 else "#8896a8")
            streak_val = str(row["STREAK"])
            streak_char = streak_val[0] if streak_val else ""
            streak_color = "#5a8f4e" if streak_char == "W" else ("#87ceeb" if streak_char == "O" else "#c41e3a" if streak_char == "L" else "#8896a8")
            bg = "rgba(255,255,255,0.02)" if idx % 2 == 0 else "transparent"
            rows_html += (
                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);background:{bg};">'
                f'<td style="padding:6px 14px;white-space:nowrap;">'
                f'<span style="color:rgba(255,255,255,0.2);font-size:11px;margin-right:4px;">{idx+1}</span>'
                f'{badge}'
                f'<a href="/4_Teams?team={row["teamAbbrev"]}" target="_self" '
                f'style="color:#fff;font-weight:600;font-size:12px;text-decoration:none;" '
                f'onmouseover="this.style.color=\'#5a8f4e\'" onmouseout="this.style.color=\'#fff\'">'
                f'{row["teamAbbrev"]}</a>'
                f'</td>'
                f'<td style="text-align:center;padding:6px 6px;color:#8896a8;font-size:12px;">{int(row["gamesPlayed"])}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:#fff;font-weight:600;font-size:12px;">{int(row["wins"])}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:#8896a8;font-size:12px;">{int(row["losses"])}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:#8896a8;font-size:12px;">{int(row["otLosses"])}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:#5a8f4e;font-weight:700;font-size:12px;">{int(row["points"])}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:{diff_color};font-family:monospace;font-size:11px;font-weight:700;">{diff_str}</td>'
                f'<td style="text-align:center;padding:6px 6px;color:{pp_color};font-family:monospace;font-size:11px;">{pp_val:.1f}%</td>'
                f'<td style="text-align:center;padding:6px 6px;color:{pk_color};font-family:monospace;font-size:11px;">{pk_val:.1f}%</td>'
                f'<td style="text-align:center;padding:6px 6px;color:{streak_color};font-family:monospace;font-size:11px;font-weight:700;">{streak_val}</td>'
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
            f'<th style="text-align:center;padding:7px 6px;color:#f97316;font-size:10px;font-weight:600;">PP%</th>'
            f'<th style="text-align:center;padding:7px 6px;color:#87ceeb;font-size:10px;font-weight:600;">PK%</th>'
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

    data_source_footer("Standings recalculated each morning from official NHL data")

# ══════════════════════════════════════════════════════════════════════════════
# Generic standings for all other leagues
# ══════════════════════════════════════════════════════════════════════════════
else:
    try:
        df = get_standings(active_league)
    except Exception as e:
        st.error(f"Could not load standings: {e}")
        st.stop()

    if df.empty:
        st.warning(f"No standings data available for {league_label}.")
        st.stop()

    # ── Render as styled HTML table ───────────────────────────────────────────
    # Normalise column names to a common set where possible
    col_map = {
        # SHL has ranking, season cols
        "ranking": "rank", "pts": "pts", "points": "pts",
        "wins": "w", "losses": "l", "otl": "otl",
        "gp": "gp", "gf": "gf", "ga": "ga", "diff": "diff",
        "pp_pct": "pp%",
        # MET
        "otw": "otw",
        # NOR/SUI/SWE already normalised by get_standings
    }
    df_display = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Determine which columns exist for the header
    priority_cols = ["rank", "team", "season", "gp", "w", "otw", "otl", "l", "pts", "gf", "ga", "diff", "pp%"]
    show_cols = [c for c in priority_cols if c in df_display.columns]
    remaining = [c for c in df_display.columns if c not in show_cols]
    show_cols = show_cols + remaining

    # Build HTML table
    header_cells = "".join(
        f'<th style="text-align:{"left" if c == "team" else "center"};padding:7px {"14px" if c == "team" else "8px"};'
        f'color:{"#5a8f4e" if c == "pts" else "#8896a8"};font-size:10px;font-weight:{"700" if c == "pts" else "600"};'
        f'text-transform:uppercase;letter-spacing:0.06em;">{c.upper()}</th>'
        for c in show_cols
    )

    rows_html = ""
    for row_idx, (_, row) in enumerate(df_display[show_cols].iterrows()):
        bg = "rgba(255,255,255,0.02)" if row_idx % 2 == 0 else "transparent"
        cells = ""
        for col in show_cols:
            val = row[col]
            is_pts = col == "pts"
            is_diff = col == "diff"
            align = "left" if col == "team" else "center"
            padding = "6px 14px" if col == "team" else "6px 8px"

            if is_pts:
                color = "#5a8f4e"
                weight = "700"
            elif is_diff and isinstance(val, (int, float)):
                color = "#5a8f4e" if val >= 0 else "#c41e3a"
                weight = "700"
                val = f"+{int(val)}" if val > 0 else str(int(val))
            elif col in ("w", "wins"):
                color = "#fff"
                weight = "600"
            else:
                color = "#8896a8"
                weight = "400"

            # Format floats
            if isinstance(val, float):
                val = f"{val:.1f}"
            elif isinstance(val, (int,)) and not isinstance(val, bool):
                val = str(int(val))
            else:
                val = str(val) if val is not None else "—"

            cells += (
                f'<td style="text-align:{align};padding:{padding};color:{color};'
                f'font-size:12px;font-weight:{weight};white-space:nowrap;">{val}</td>'
            )
        rows_html += f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);background:{bg};">{cells}</tr>'

    table_html = (
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;margin-top:8px;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'{header_cells}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>'
    )

    st.html(table_html)

    data_source_footer(f"{league_label} standings computed from game results")
