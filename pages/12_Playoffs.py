"""Playoffs – bracket visualization for every season since 2009-10."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, data_source_footer

st.set_page_config(page_title="Playoffs – THA Analytics", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

# ── Season picker ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _seasons() -> list[int]:
    df = query("SELECT DISTINCT season FROM playoff_brackets ORDER BY season DESC")
    return df["season"].tolist()

seasons = _seasons()

def season_label(s: int) -> str:
    y = str(s)[:4]
    return f"{y}-{str(int(y)+1)[2:]}"

season_labels = [season_label(s) for s in seasons]

# Default to latest complete season (not the one with all 0-0 scores)
@st.cache_data(ttl=3600, show_spinner=False)
def _latest_complete() -> int:
    df = query("""
        SELECT season FROM playoff_brackets
        WHERE winning_team_id IS NOT NULL AND playoff_round = 4
        ORDER BY season DESC LIMIT 1
    """)
    return int(df.iloc[0]["season"]) if not df.empty else seasons[0]

default_season = _latest_complete()
default_idx = seasons.index(default_season) if default_season in seasons else 0

col_pick, col_status = st.columns([2, 4])
with col_pick:
    chosen_label = st.selectbox(
        "", season_labels,
        index=default_idx,
        label_visibility="collapsed",
        key="po_season",
    )

season = seasons[season_labels.index(chosen_label)]
page_header("Playoffs", f"{chosen_label} · Stanley Cup bracket", data_date=get_data_date())

# ── Load bracket ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _bracket(s: int) -> pd.DataFrame:
    return query(f"""
        SELECT playoff_round, series_letter, series_title,
               top_seed_rank, top_seed_team_abbr, top_seed_wins,
               bottom_seed_rank, bottom_seed_team_abbr, bottom_seed_wins,
               winning_team_id, top_seed_team_id, bottom_seed_team_id
        FROM playoff_brackets
        WHERE season = {s}
        ORDER BY playoff_round, series_letter
    """)

df_bracket = _bracket(season)

# ── Helpers ────────────────────────────────────────────────────────────────────
CONF_EAST = {"A", "B", "C", "D", "I", "J", "M"}
CONF_WEST = {"E", "F", "G", "H", "K", "L", "N"}
ROUND_NAMES = {1: "First Round", 2: "Second Round", 3: "Conference Finals", 4: "Stanley Cup Final"}

def _winner_abbr(row) -> str | None:
    wid = row["winning_team_id"]
    if pd.isna(wid):
        return None
    if row["top_seed_team_id"] == wid:
        return row["top_seed_team_abbr"]
    return row["bottom_seed_team_abbr"]

def _series_status(row) -> str:
    tw = int(row["top_seed_wins"])
    bw = int(row["bottom_seed_wins"])
    winner = _winner_abbr(row)
    if winner:
        return f"{winner} wins {max(tw,bw)}-{min(tw,bw)}"
    total = tw + bw
    if total == 0:
        return "Not started"
    return f"Series tied {tw}-{bw}" if tw == bw else f"Leads {max(tw,bw)}-{min(tw,bw)}"

def _series_card(row, round_label: str = "") -> str:
    """Return HTML for one series matchup card."""
    top  = str(row["top_seed_team_abbr"]  or "TBD")
    bot  = str(row["bottom_seed_team_abbr"] or "TBD")
    tw   = int(row["top_seed_wins"])
    bw   = int(row["bottom_seed_wins"])
    winner = _winner_abbr(row)
    status = _series_status(row)
    in_progress = winner is None and (tw + bw) > 0
    not_started = winner is None and (tw + bw) == 0

    top_is_winner = winner == top
    bot_is_winner = winner == bot

    # Colors
    top_name_color = "#fff" if top_is_winner else ("#5a8f4e" if top_is_winner else ("#8896a8" if (bot_is_winner or not_started) else "#f1f5f9"))
    bot_name_color = "#fff" if bot_is_winner else ("#8896a8" if (top_is_winner or not_started) else "#f1f5f9")
    top_name_color = "#fff" if not winner else ("#5a8f4e" if top_is_winner else "#8896a8")
    bot_name_color = "#fff" if not winner else ("#5a8f4e" if bot_is_winner else "#8896a8")
    if not_started:
        top_name_color = bot_name_color = "#f1f5f9"

    top_w_color = "#f97316" if top_is_winner else ("#fff" if in_progress else "#8896a8")
    bot_w_color = "#f97316" if bot_is_winner else ("#fff" if in_progress else "#8896a8")

    top_rank = int(row["top_seed_rank"]) if pd.notna(row["top_seed_rank"]) else ""
    bot_rank = int(row["bottom_seed_rank"]) if pd.notna(row["bottom_seed_rank"]) else ""

    # Trophy indicator for Cup winner
    trophy = " 🏆" if (round_label == "Stanley Cup Final" and winner) else ""

    status_color = "#5a8f4e" if winner else ("#f97316" if in_progress else "#8896a8")

    border_color = "#5a8f4e" if winner else ("rgba(249,115,22,0.4)" if in_progress else "rgba(255,255,255,0.08)")
    bg_color     = "rgba(90,143,78,0.05)" if winner else ("rgba(249,115,22,0.03)" if in_progress else "rgba(255,255,255,0.02)")

    return f"""
    <div style="background:{bg_color};border:1px solid {border_color};
                border-radius:6px;padding:10px 12px;margin-bottom:8px;min-width:150px;">
      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">{round_label}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:5px;">
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="color:rgba(255,255,255,0.2);font-size:10px;width:14px;">{top_rank}</span>
          <span style="color:{top_name_color};font-weight:700;font-size:13px;font-family:monospace;">{top}{trophy if top_is_winner else ''}</span>
        </div>
        <span style="color:{top_w_color};font-weight:800;font-size:16px;font-family:monospace;min-width:18px;text-align:right;">{tw}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="color:rgba(255,255,255,0.2);font-size:10px;width:14px;">{bot_rank}</span>
          <span style="color:{bot_name_color};font-weight:700;font-size:13px;font-family:monospace;">{bot}{trophy if bot_is_winner else ''}</span>
        </div>
        <span style="color:{bot_w_color};font-weight:800;font-size:16px;font-family:monospace;min-width:18px;text-align:right;">{bw}</span>
      </div>
      <div style="margin-top:7px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.06);
                  color:{status_color};font-size:10px;">{status}</div>
    </div>
    """

def _round_header(label: str, conf: str = "") -> str:
    sub = f" <span style='color:#8896a8;font-size:10px;'>· {conf}</span>" if conf else ""
    return (
        f"<p style='color:#fff;font-size:11px;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.08em;margin:0 0 10px;'>{label}{sub}</p>"
    )

# ── Check for play-in / qualifiers (round 0) ──────────────────────────────────
df_playin = df_bracket[df_bracket["playoff_round"] == 0]
df_main   = df_bracket[df_bracket["playoff_round"] > 0]

# ── Partition series by conference + round ─────────────────────────────────────
def get_series(rnd: int, letters: set) -> pd.DataFrame:
    return df_main[
        (df_main["playoff_round"] == rnd) &
        (df_main["series_letter"].isin(letters))
    ].sort_values("series_letter")

r1_east = get_series(1, {"A","B","C","D"})
r1_west = get_series(1, {"E","F","G","H"})
r2_east = get_series(2, {"I","J"})
r2_west = get_series(2, {"K","L"})
ecf     = get_series(3, {"M"})
wcf     = get_series(3, {"N"})
scf     = get_series(4, {"O"})

# ── Champion banner ────────────────────────────────────────────────────────────
if not scf.empty:
    scf_row = scf.iloc[0]
    cup_winner = _winner_abbr(scf_row)
    if cup_winner:
        st.html(f"""
        <div style="background:linear-gradient(135deg,rgba(90,143,78,0.12),rgba(249,115,22,0.06));
                    border:1px solid rgba(90,143,78,0.3);border-radius:8px;
                    padding:16px 24px;margin-bottom:24px;display:flex;
                    align-items:center;gap:16px;">
          <div style="font-size:32px;">🏆</div>
          <div>
            <div style="color:#5a8f4e;font-size:10px;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:2px;">{chosen_label} Stanley Cup Champion</div>
            <div style="color:#fff;font-weight:900;font-size:26px;letter-spacing:-0.02em;
                        font-family:monospace;">{cup_winner}</div>
          </div>
        </div>
        """)
    elif (int(scf_row["top_seed_wins"]) + int(scf_row["bottom_seed_wins"])) > 0:
        # In progress
        top = scf_row["top_seed_team_abbr"]
        bot = scf_row["bottom_seed_team_abbr"]
        tw  = int(scf_row["top_seed_wins"])
        bw  = int(scf_row["bottom_seed_wins"])
        st.html(f"""
        <div style="background:rgba(249,115,22,0.06);border:1px solid rgba(249,115,22,0.3);
                    border-radius:8px;padding:16px 24px;margin-bottom:24px;">
          <div style="color:#f97316;font-size:10px;font-weight:600;text-transform:uppercase;
                      letter-spacing:0.1em;margin-bottom:4px;">Stanley Cup Final · In Progress</div>
          <div style="color:#fff;font-weight:900;font-size:22px;letter-spacing:-0.02em;font-family:monospace;">
            {top} <span style="color:#f97316">{tw}</span>
            <span style="color:#8896a8;font-size:14px;"> vs </span>
            <span style="color:#f97316">{bw}</span> {bot}
          </div>
        </div>
        """)

# ── Main bracket: 5-column layout ─────────────────────────────────────────────
# Col layout: R1 East | R2 East | Finals | R2 West | R1 West
col_r1e, col_r2e, col_finals, col_r2w, col_r1w = st.columns([2, 1.5, 2, 1.5, 2], gap="medium")

with col_r1e:
    st.markdown(_round_header("First Round", "Eastern"), unsafe_allow_html=True)
    for _, row in r1_east.iterrows():
        st.html(_series_card(row, ""))

with col_r2e:
    st.markdown(_round_header("Second Round", "Eastern"), unsafe_allow_html=True)
    for _, row in r2_east.iterrows():
        st.html(_series_card(row, ""))

with col_finals:
    # ECF
    st.markdown(_round_header("Conference Finals"), unsafe_allow_html=True)
    for _, row in ecf.iterrows():
        st.html(_series_card(row, "Eastern Conf. Final"))
    for _, row in wcf.iterrows():
        st.html(_series_card(row, "Western Conf. Final"))

    # SCF
    st.markdown(
        "<p style='color:#5a8f4e;font-size:11px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.08em;margin:16px 0 10px;'>Stanley Cup Final</p>",
        unsafe_allow_html=True,
    )
    for _, row in scf.iterrows():
        st.html(_series_card(row, "Stanley Cup Final"))

with col_r2w:
    st.markdown(_round_header("Second Round", "Western"), unsafe_allow_html=True)
    for _, row in r2_west.iterrows():
        st.html(_series_card(row, ""))

with col_r1w:
    st.markdown(_round_header("First Round", "Western"), unsafe_allow_html=True)
    for _, row in r1_west.iterrows():
        st.html(_series_card(row, ""))

# ── Play-in / Qualifiers ───────────────────────────────────────────────────────
if not df_playin.empty:
    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.08);margin:24px 0 16px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#f97316;font-size:11px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.08em;margin-bottom:12px;'>Qualifying Round (COVID bubble)</p>",
        unsafe_allow_html=True,
    )
    qi_cols = st.columns(4)
    for i, (_, row) in enumerate(df_playin.iterrows()):
        with qi_cols[i % 4]:
            st.html(_series_card(row, "Qualifier"))

# ── Historical results table ───────────────────────────────────────────────────
with st.expander("All series results", expanded=False):
    rows_html = ""
    for _, row in df_main.sort_values(["playoff_round","series_letter"]).iterrows():
        winner = _winner_abbr(row)
        top = str(row["top_seed_team_abbr"] or "TBD")
        bot = str(row["bottom_seed_team_abbr"] or "TBD")
        tw  = int(row["top_seed_wins"])
        bw  = int(row["bottom_seed_wins"])
        rnd_name = ROUND_NAMES.get(int(row["playoff_round"]), "")
        w_color = "#5a8f4e" if winner else "#8896a8"
        result_str = f"{winner} wins {max(tw,bw)}-{min(tw,bw)}" if winner else _series_status(row)
        rows_html += (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<td style="padding:7px 14px;color:#8896a8;font-size:11px;">{rnd_name}</td>'
            f'<td style="padding:7px 8px;color:#fff;font-weight:600;font-family:monospace;font-size:12px;">{top}</td>'
            f'<td style="padding:7px 8px;color:#8896a8;font-size:11px;text-align:center;">{tw}–{bw}</td>'
            f'<td style="padding:7px 8px;color:#fff;font-weight:600;font-family:monospace;font-size:12px;">{bot}</td>'
            f'<td style="padding:7px 14px;color:{w_color};font-size:11px;">{result_str}</td>'
            f'</tr>'
        )
    st.html(
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'<th style="padding:7px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">Round</th>'
        f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">Top seed</th>'
        f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">Result</th>'
        f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">Bottom seed</th>'
        f'<th style="padding:7px 14px;color:#5a8f4e;font-size:10px;font-weight:600;text-align:left;">Winner</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
    )

# ── Stanley Cup winners strip ──────────────────────────────────────────────────
st.markdown(
    "<hr style='border-color:rgba(255,255,255,0.08);margin:24px 0 16px;'>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;margin-bottom:10px;'>Stanley Cup Champions 2009–present</p>",
    unsafe_allow_html=True,
)

@st.cache_data(ttl=3600, show_spinner=False)
def _cup_winners() -> pd.DataFrame:
    return query("""
        SELECT pb.season,
               CASE WHEN pb.top_seed_team_id = pb.winning_team_id
                    THEN pb.top_seed_team_abbr
                    ELSE pb.bottom_seed_team_abbr END AS champion
        FROM playoff_brackets pb
        WHERE pb.playoff_round = 4 AND pb.winning_team_id IS NOT NULL
        ORDER BY pb.season DESC
    """)

df_cups = _cup_winners()
chips_html = ""
for _, r in df_cups.iterrows():
    lbl = season_label(int(r["season"]))
    is_current = int(r["season"]) == season
    bg = "rgba(90,143,78,0.2)" if is_current else "rgba(255,255,255,0.04)"
    border = "rgba(90,143,78,0.5)" if is_current else "rgba(255,255,255,0.08)"
    champ_c = "#5a8f4e" if is_current else "#fff"
    chips_html += (
        f'<div style="background:{bg};border:1px solid {border};border-radius:5px;'
        f'padding:6px 10px;text-align:center;min-width:60px;">'
        f'<div style="color:#8896a8;font-size:9px;">{lbl}</div>'
        f'<div style="color:{champ_c};font-weight:800;font-size:12px;font-family:monospace;">{r["champion"]}</div>'
        f'</div>'
    )

st.markdown(
    f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{chips_html}</div>',
    unsafe_allow_html=True,
)

data_source_footer()
