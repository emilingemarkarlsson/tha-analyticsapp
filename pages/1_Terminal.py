"""THA Terminal – dense analytics dashboard inspired by trading terminals."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query, query_fresh, get_data_date
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.components import page_header, data_source_footer

st.set_page_config(page_title="Terminal – THA Analytics", layout="wide")
_render_sidebar()
require_login()

# ── Terminal CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tighter spacing for terminal feel */
[data-testid="block-container"] { padding-top: 1rem !important; }
.term-table { font-family: 'SF Mono', 'Fira Code', monospace; }
.term-row:hover { background: rgba(255,255,255,0.05) !important; }
</style>
""", unsafe_allow_html=True)

page_header("Terminal", "All players · All teams · All stats", data_date=get_data_date())

# ── Tab navigation (pill style) ────────────────────────────────────────────────
TABS = ["Skaters", "Goalies", "Teams"]
if "term_tab" not in st.session_state:
    st.session_state.term_tab = "Skaters"

tab_cols = st.columns(len(TABS) + 6)
for i, t in enumerate(TABS):
    active = st.session_state.term_tab == t
    bg     = "#5a8f4e" if active else "rgba(255,255,255,0.05)"
    fg     = "#fff"    if active else "#8896a8"
    border = "#5a8f4e" if active else "rgba(255,255,255,0.1)"
    with tab_cols[i]:
        if st.button(t, key=f"tab_{t}", use_container_width=True):
            st.session_state.term_tab   = t
            st.session_state.term_sel   = None
            st.rerun()

st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

tab = st.session_state.term_tab

# ══════════════════════════════════════════════════════════════════════════════
#  SKATERS TAB
# ══════════════════════════════════════════════════════════════════════════════
if tab == "Skaters":
    # ── Presets ────────────────────────────────────────────────────────────────
    PRESETS = {
        "All":          dict(pos=["C","L","R","D"], min_gp=10, z_min=-4, z_max=4,  min_toi=0),
        "Hot Streak":   dict(pos=["C","L","R","D"], min_gp=20, z_min=0.8, z_max=4, min_toi=10),
        "Cold Spell":   dict(pos=["C","L","R","D"], min_gp=20, z_min=-4, z_max=-0.8, min_toi=10),
        "PPG Leaders":  dict(pos=["C","L","R"],     min_gp=20, z_min=-4, z_max=4,  min_toi=8),
        "Shutdown D":   dict(pos=["D"],             min_gp=20, z_min=-4, z_max=4,  min_toi=18),
        "Breakout":     dict(pos=["C","L","R"],     min_gp=10, z_min=0.5, z_max=4, min_toi=8),
    }
    preset_cols = st.columns(len(PRESETS))
    active_preset = st.session_state.get("term_preset", "All")
    for i, (label, cfg) in enumerate(PRESETS.items()):
        with preset_cols[i]:
            if st.button(label, key=f"sp_{label}", use_container_width=True):
                st.session_state["term_preset"] = label
                if cfg:
                    st.session_state["term_pos"]    = cfg["pos"]
                    st.session_state["term_min_gp"] = cfg["min_gp"]
                    st.session_state["term_z_min"]  = cfg["z_min"]
                    st.session_state["term_z_max"]  = cfg["z_max"]
                    st.session_state["term_min_toi"]= cfg["min_toi"]
                st.rerun()

    # ── Filters ────────────────────────────────────────────────────────────────
    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
        with fc1:
            s_search = st.text_input("Search", placeholder="Player or team...",
                                     label_visibility="collapsed", key="term_search")
        with fc2:
            s_pos = st.multiselect("Pos", ["C","L","R","D"], default=["C","L","R","D"],
                                   label_visibility="collapsed", key="term_pos")
        with fc3:
            s_gp  = st.slider("Min GP", 1, 82, 10, label_visibility="collapsed", key="term_min_gp")
        with fc4:
            s_sort = st.selectbox("Sort by", [
                "pts_zscore_5v20", "pts_avg_5g", "pts_season", "goals_season",
                "plusMinus", "ppPoints", "toi_avg",
            ], format_func=lambda x: {
                "pts_zscore_5v20": "Form (σ)",
                "pts_avg_5g":      "PTS/5g",
                "pts_season":      "PTS season",
                "goals_season":    "Goals",
                "plusMinus":       "+/-",
                "ppPoints":        "PP Points",
                "toi_avg":         "TOI/g",
            }.get(x, x), label_visibility="collapsed", key="term_sort")

    s_pos    = st.session_state.get("term_pos",    ["C","L","R","D"])
    s_gp     = st.session_state.get("term_min_gp", 10)
    s_sort   = st.session_state.get("term_sort",   "pts_zscore_5v20")
    s_search = st.session_state.get("term_search", "")
    z_min    = st.session_state.get("term_z_min",  -4.0)
    z_max    = st.session_state.get("term_z_max",   4.0)
    min_toi  = st.session_state.get("term_min_toi", 0.0)

    pos_filter = "','".join(s_pos)

    @st.cache_data(ttl=900, show_spinner=False)
    def load_skaters(pos_f, min_gp, z_min, z_max, min_toi) -> pd.DataFrame:
        return query(f"""
            SELECT CAST(pr.player_id AS VARCHAR) AS player_id,
                   pr.player_first_name || ' ' || pr.player_last_name AS name,
                   pr.team_abbr,
                   pr.position,
                   pr.gp_season                               AS gp,
                   pr.goals_season                            AS goals,
                   pr.assists_season                          AS assists,
                   pr.pts_season                              AS pts_season,
                   ROUND(pr.pts_avg_5g, 2)                   AS pts_avg_5g,
                   ROUND(pr.pts_avg_20g, 2)                  AS pts_avg_20g,
                   ROUND(pr.pts_zscore_5v20, 2)              AS pts_zscore_5v20,
                   ROUND(pr.toi_avg_10g / 60.0, 1)           AS toi_avg,
                   ss.plusMinus,
                   ss.ppPoints,
                   ROUND(ss.shootingPct * 100, 1)             AS sh_pct,
                   ROUND(ss.faceoffWinPct * 100, 1)           AS fo_pct
            FROM player_rolling_stats pr
            LEFT JOIN skater_stats ss
                   ON ss.playerId = pr.player_id AND ss.season = pr.season
            WHERE pr.game_recency_rank = 1
              AND pr.season = (SELECT MAX(season) FROM games WHERE game_type = '2')
              AND pr.gp_season >= {min_gp}
              AND pr.position IN ('{pos_f}')
              AND pr.pts_zscore_5v20 BETWEEN {z_min} AND {z_max}
              AND pr.toi_avg_10g / 60.0 >= {min_toi}
              AND pr.player_first_name IS NOT NULL
            ORDER BY pr.pts_zscore_5v20 DESC
            LIMIT 500
        """)

    df_s = load_skaters(pos_filter, s_gp, z_min, z_max, min_toi)

    if s_search:
        q = s_search.lower()
        df_s = df_s[
            df_s["name"].str.lower().str.contains(q, na=False) |
            df_s["team_abbr"].str.lower().str.contains(q, na=False)
        ]

    asc = s_sort in ("fo_pct",)
    if s_sort in df_s.columns:
        df_s = df_s.sort_values(s_sort, ascending=asc, na_position="last")
    df_s = df_s.reset_index(drop=True)

    # ── Layout: table (left) + detail card (right) ─────────────────────────────
    col_table, col_detail = st.columns([3, 1], gap="large")

    with col_table:
        st.markdown(
            f"<p style='color:#8896a8;font-size:11px;margin-bottom:6px;'>"
            f"<b style='color:#fff;'>{len(df_s)}</b> players</p>",
            unsafe_allow_html=True,
        )

        rows_html = ""
        for idx, row in df_s.head(200).iterrows():
            z   = float(row["pts_zscore_5v20"])
            z_c = "#f97316" if z >= 1.5 else ("#5a8f4e" if z >= 0.5 else ("#87ceeb" if z <= -1.5 else ("#3b82f6" if z <= -0.5 else "#8896a8")))
            z_s = f"+{z:.2f}" if z >= 0 else f"{z:.2f}"
            pm  = row["plusMinus"]
            pm_s = (f'+{int(pm)}' if pm > 0 else str(int(pm))) if pd.notna(pm) else "—"
            pm_c = "#5a8f4e" if (pd.notna(pm) and pm > 0) else ("#c41e3a" if (pd.notna(pm) and pm < 0) else "#8896a8")
            pp  = int(row["ppPoints"]) if pd.notna(row["ppPoints"]) else "—"
            sh  = f'{row["sh_pct"]:.1f}%' if pd.notna(row["sh_pct"]) else "—"
            fo  = f'{row["fo_pct"]:.1f}%' if pd.notna(row["fo_pct"]) and float(row["fo_pct"]) > 0 else "—"
            toi = f'{row["toi_avg"]:.1f}' if pd.notna(row["toi_avg"]) else "—"
            is_sel = st.session_state.get("term_sel") == row["player_id"]
            bg = "rgba(90,143,78,0.08)" if is_sel else ("rgba(255,255,255,0.015)" if idx % 2 == 0 else "transparent")

            rows_html += (
                f'<tr class="term-row" style="border-bottom:1px solid rgba(255,255,255,0.035);background:{bg};">'
                f'<td style="padding:6px 10px;color:#8896a8;font-family:monospace;font-size:10px;">{idx+1}</td>'
                f'<td style="padding:6px 6px;white-space:nowrap;">'
                f'<span style="color:#fff;font-weight:600;font-size:11px;">{row["name"]}</span>'
                f'</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:10px;font-family:monospace;">{row["team_abbr"]}</td>'
                f'<td style="padding:6px 4px;color:#8896a8;font-size:10px;">{row["position"]}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(row["gp"])}</td>'
                f'<td style="padding:6px 6px;color:#fff;font-size:11px;text-align:right;">{int(row["goals"])}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(row["assists"])}</td>'
                f'<td style="padding:6px 6px;color:#5a8f4e;font-weight:700;font-size:11px;text-align:right;">{int(row["pts_season"])}</td>'
                f'<td style="padding:6px 6px;color:{pm_c};font-family:monospace;font-size:11px;text-align:right;">{pm_s}</td>'
                f'<td style="padding:6px 6px;color:#87ceeb;font-size:11px;text-align:right;">{pp}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:10px;text-align:right;">{sh}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:10px;text-align:right;">{toi}</td>'
                f'<td style="padding:6px 8px;color:{z_c};font-family:monospace;font-weight:800;font-size:12px;text-align:right;">{z_s}σ</td>'
                f'<td style="padding:6px 4px;color:#8896a8;font-family:monospace;font-size:10px;text-align:right;">{row["pts_avg_5g"]:.2f}</td>'
                f'<td style="padding:6px 10px;color:#8896a8;font-family:monospace;font-size:10px;text-align:right;">{row["pts_avg_20g"]:.2f}</td>'
                f'</tr>'
            )

        st.html(
            f'<div style="overflow-x:auto;">'
            f'<table class="term-table" style="width:100%;border-collapse:collapse;min-width:700px;">'
            f'<thead><tr style="background:rgba(255,255,255,0.04);border-bottom:2px solid rgba(255,255,255,0.1);">'
            f'<th style="padding:6px 10px;color:#8896a8;font-size:9px;text-align:left;">#</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:left;">PLAYER</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;">TM</th>'
            f'<th style="padding:6px 4px;color:#8896a8;font-size:9px;">POS</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">GP</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">G</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">A</th>'
            f'<th style="padding:6px 6px;color:#5a8f4e;font-size:9px;text-align:right;">PTS</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">+/-</th>'
            f'<th style="padding:6px 6px;color:#87ceeb;font-size:9px;text-align:right;">PPP</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">SH%</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">TOI</th>'
            f'<th style="padding:6px 8px;color:#f97316;font-size:9px;text-align:right;">FORM σ</th>'
            f'<th style="padding:6px 4px;color:#8896a8;font-size:9px;text-align:right;">5g</th>'
            f'<th style="padding:6px 10px;color:#8896a8;font-size:9px;text-align:right;">20g</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
        )

        if len(df_s) > 200:
            st.markdown(
                f"<p style='color:#8896a8;font-size:11px;margin-top:6px;'>"
                f"Showing 200 of {len(df_s)} players. Use filters to narrow down.</p>",
                unsafe_allow_html=True,
            )

    # ── Detail panel ───────────────────────────────────────────────────────────
    with col_detail:
        st.markdown(
            "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Quick Select</p>",
            unsafe_allow_html=True,
        )
        sel_options = {f"{r['name']}  ({r['team_abbr']})": r["player_id"]
                       for _, r in df_s.head(50).iterrows()}
        if sel_options:
            chosen_label = st.selectbox("", list(sel_options.keys()),
                                        label_visibility="collapsed", key="term_sel_box_s")
            sel_pid = sel_options[chosen_label]

            # Load detail
            d = df_s[df_s["player_id"] == sel_pid]
            if not d.empty:
                d = d.iloc[0]
                z   = float(d["pts_zscore_5v20"])
                z_c = "#f97316" if z >= 1.5 else ("#5a8f4e" if z >= 0.5 else ("#87ceeb" if z <= -0.5 else "#8896a8"))
                z_s = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"

                # Fetch AI insight for player
                df_ins = query_fresh(f"""
                    SELECT headline, insight_type, zscore
                    FROM agent_insights
                    WHERE entity_name ILIKE '%{d["name"].split()[0]}%'
                       OR entity_name ILIKE '%{d["name"].split()[-1]}%'
                    ORDER BY generated_at DESC LIMIT 1
                """)

                bio = query_fresh(f"SELECT headshot, birthCountry FROM players WHERE id={sel_pid} LIMIT 1")
                headshot = str(bio.iloc[0]["headshot"]) if not bio.empty and bio.iloc[0]["headshot"] else ""

                img_html = (
                    f'<img src="{headshot}" style="width:56px;height:56px;border-radius:50%;'
                    f'object-fit:cover;border:2px solid {z_c}33;" onerror="this.style.display=\'none\'">'
                    if headshot else
                    f'<div style="width:56px;height:56px;border-radius:50%;background:#5a8f4e;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-weight:900;font-size:20px;color:#fff;">{d["name"][0]}</div>'
                )

                pp  = int(d["ppPoints"]) if pd.notna(d["ppPoints"]) else "—"
                pm  = (f'+{int(d["plusMinus"])}' if d["plusMinus"] > 0 else str(int(d["plusMinus"]))) if pd.notna(d["plusMinus"]) else "—"

                st.html(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                            border-radius:6px;padding:14px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                    {img_html}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:13px;">{d['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">{d['position']} · {d['team_abbr']}</div>
                      <div style="color:{z_c};font-weight:800;font-size:14px;font-family:monospace;">{z_s}</div>
                    </div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">PTS</div>
                      <div style="color:#5a8f4e;font-weight:800;font-size:16px;">{int(d['pts_season'])}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">+/-</div>
                      <div style="color:#fff;font-weight:800;font-size:16px;">{pm}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">PTS/5g</div>
                      <div style="color:#f97316;font-weight:800;font-size:16px;">{d['pts_avg_5g']:.2f}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">PPP</div>
                      <div style="color:#87ceeb;font-weight:800;font-size:16px;">{pp}</div>
                    </div>
                  </div>
                  {"<div style='margin-top:10px;background:rgba(255,255,255,0.02);border-radius:4px;padding:8px;'><div style='color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:3px;'>AI Insight</div><div style='color:#8896a8;font-size:10px;line-height:1.5;'>" + str(df_ins.iloc[0]['headline']) + "</div></div>" if not df_ins.empty else ""}
                  <div style="margin-top:10px;">
                    <a href="/Player_History" target="_self"
                       style="color:#5a8f4e;font-size:10px;text-decoration:underline;
                              text-underline-offset:3px;">View full career →</a>
                  </div>
                </div>
                """)

# ══════════════════════════════════════════════════════════════════════════════
#  GOALIES TAB
# ══════════════════════════════════════════════════════════════════════════════
elif tab == "Goalies":
    with st.expander("Filters", expanded=False):
        gc1, gc2 = st.columns([2, 1])
        with gc1:
            g_search = st.text_input("Search", placeholder="Goalie name or team...",
                                     label_visibility="collapsed", key="term_g_search")
        with gc2:
            g_min_gp = st.slider("Min GP", 1, 82, 5,
                                 label_visibility="collapsed", key="term_g_min_gp")
        g_sort = st.selectbox("Sort", [
            "z", "sv_pct", "gaa", "wins", "sv_5g", "gp",
        ], format_func=lambda x: {
            "z":      "Form (σ)",
            "sv_pct": "Sv% season",
            "gaa":    "GAA",
            "wins":   "Wins",
            "sv_5g":  "Sv% / 5g",
            "gp":     "GP",
        }.get(x, x), label_visibility="collapsed", key="term_g_sort")

    g_search = st.session_state.get("term_g_search", "")
    g_min_gp = st.session_state.get("term_g_min_gp", 5)
    g_sort   = st.session_state.get("term_g_sort", "z")

    @st.cache_data(ttl=900, show_spinner=False)
    def load_goalies(min_gp) -> pd.DataFrame:
        return query(f"""
            SELECT CAST(gr.player_id AS VARCHAR) AS player_id,
                   gr.player_first_name || ' ' || gr.player_last_name AS name,
                   gr.team_abbr,
                   gr.gp_season AS gp,
                   gs.wins, gs.losses, gs.otLosses,
                   ROUND(gs.savePct * 100, 3) AS sv_pct,
                   ROUND(gs.goalsAgainstAverage, 2) AS gaa,
                   gs.shutouts,
                   ROUND(gr.sv_pct_avg_5g * 100, 2) AS sv_5g,
                   ROUND(gr.sv_pct_avg_20g * 100, 2) AS sv_20g,
                   ROUND(gr.sv_pct_zscore_5v20, 2) AS z
            FROM goalie_rolling_stats gr
            LEFT JOIN goalie_stats gs
                   ON gs.playerId = gr.player_id AND gs.season = gr.season
            WHERE gr.game_recency_rank = 1
              AND gr.gp_season >= {min_gp}
              AND gr.player_first_name IS NOT NULL
        """)

    df_g = load_goalies(g_min_gp)
    if g_search:
        q = g_search.lower()
        df_g = df_g[
            df_g["name"].str.lower().str.contains(q, na=False) |
            df_g["team_abbr"].str.lower().str.contains(q, na=False)
        ]

    asc_g = g_sort in ("gaa",)
    if g_sort in df_g.columns:
        df_g = df_g.sort_values(g_sort, ascending=asc_g, na_position="last")
    df_g = df_g.reset_index(drop=True)

    col_gtable, col_gdetail = st.columns([3, 1], gap="large")

    with col_gtable:
        st.markdown(
            f"<p style='color:#8896a8;font-size:11px;margin-bottom:6px;'>"
            f"<b style='color:#fff;'>{len(df_g)}</b> goalies</p>",
            unsafe_allow_html=True,
        )

        rows_html = ""
        for idx, row in df_g.iterrows():
            z   = float(row["z"]) if pd.notna(row["z"]) else 0.0
            z_c = "#f97316" if z >= 1.0 else ("#5a8f4e" if z >= 0.3 else ("#87ceeb" if z <= -0.3 else "#8896a8"))
            z_s = f"+{z:.2f}" if z >= 0 else f"{z:.2f}"
            sv  = float(row["sv_pct"]) if pd.notna(row["sv_pct"]) else 0.0
            sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else ("#8896a8" if sv >= 89.5 else "#87ceeb"))
            gaa = float(row["gaa"]) if pd.notna(row["gaa"]) else 0.0
            gaa_c = "#5a8f4e" if gaa <= 2.5 else ("#8896a8" if gaa <= 3.0 else "#c41e3a")
            w   = int(row["wins"])     if pd.notna(row["wins"])     else 0
            l   = int(row["losses"])   if pd.notna(row["losses"])   else 0
            otl = int(row["otLosses"]) if pd.notna(row["otLosses"]) else 0
            so  = int(row["shutouts"]) if pd.notna(row["shutouts"]) else 0
            is_sel = st.session_state.get("term_sel") == row["player_id"]
            bg = "rgba(90,143,78,0.08)" if is_sel else ("rgba(255,255,255,0.015)" if idx % 2 == 0 else "transparent")

            rows_html += (
                f'<tr class="term-row" style="border-bottom:1px solid rgba(255,255,255,0.035);background:{bg};">'
                f'<td style="padding:6px 10px;color:#8896a8;font-family:monospace;font-size:10px;">{idx+1}</td>'
                f'<td style="padding:6px 6px;white-space:nowrap;">'
                f'<span style="color:#fff;font-weight:600;font-size:11px;">{row["name"]}</span>'
                f'</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:10px;font-family:monospace;">{row["team_abbr"]}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(row["gp"])}</td>'
                f'<td style="padding:6px 6px;color:#5a8f4e;font-weight:700;font-size:11px;text-align:right;">{w}</td>'
                f'<td style="padding:6px 6px;color:#c41e3a;font-size:11px;text-align:right;">{l}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{otl}</td>'
                f'<td style="padding:6px 6px;color:{sv_c};font-family:monospace;font-weight:700;font-size:11px;text-align:right;">{sv:.2f}%</td>'
                f'<td style="padding:6px 6px;color:{gaa_c};font-family:monospace;font-size:11px;text-align:right;">{gaa:.2f}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{so}</td>'
                f'<td style="padding:6px 6px;color:#87ceeb;font-family:monospace;font-size:10px;text-align:right;">{row["sv_5g"]:.2f}%</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-family:monospace;font-size:10px;text-align:right;">{row["sv_20g"]:.2f}%</td>'
                f'<td style="padding:6px 10px;color:{z_c};font-family:monospace;font-weight:800;font-size:12px;text-align:right;">{z_s}σ</td>'
                f'</tr>'
            )

        st.html(
            f'<div style="overflow-x:auto;">'
            f'<table class="term-table" style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:rgba(255,255,255,0.04);border-bottom:2px solid rgba(255,255,255,0.1);">'
            f'<th style="padding:6px 10px;color:#8896a8;font-size:9px;text-align:left;">#</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:left;">GOALIE</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;">TM</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">GP</th>'
            f'<th style="padding:6px 6px;color:#5a8f4e;font-size:9px;text-align:right;">W</th>'
            f'<th style="padding:6px 6px;color:#c41e3a;font-size:9px;text-align:right;">L</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">OTL</th>'
            f'<th style="padding:6px 6px;color:#f97316;font-size:9px;text-align:right;">Sv%</th>'
            f'<th style="padding:6px 6px;color:#87ceeb;font-size:9px;text-align:right;">GAA</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">SO</th>'
            f'<th style="padding:6px 6px;color:#87ceeb;font-size:9px;text-align:right;">Sv%/5g</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">Sv%/20g</th>'
            f'<th style="padding:6px 10px;color:#f97316;font-size:9px;text-align:right;">FORM σ</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
        )

    with col_gdetail:
        st.markdown(
            "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Quick Select</p>",
            unsafe_allow_html=True,
        )
        sel_g_options = {f"{r['name']}  ({r['team_abbr']})": r["player_id"]
                         for _, r in df_g.head(50).iterrows()}
        if sel_g_options:
            g_chosen = st.selectbox("", list(sel_g_options.keys()),
                                    label_visibility="collapsed", key="term_sel_box_g")
            gsel_pid = sel_g_options[g_chosen]
            d = df_g[df_g["player_id"] == gsel_pid]
            if not d.empty:
                d   = d.iloc[0]
                z   = float(d["z"]) if pd.notna(d["z"]) else 0.0
                z_c = "#f97316" if z >= 0.5 else ("#87ceeb" if z <= -0.3 else "#8896a8")
                z_s = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"
                sv  = float(d["sv_pct"]) if pd.notna(d["sv_pct"]) else 0.0
                sv_c = "#f97316" if sv >= 92 else ("#5a8f4e" if sv >= 91 else "#8896a8")

                bio = query_fresh(f"SELECT headshot FROM players WHERE id={gsel_pid} LIMIT 1")
                headshot = str(bio.iloc[0]["headshot"]) if not bio.empty and bio.iloc[0]["headshot"] else ""
                img_html = (
                    f'<img src="{headshot}" style="width:56px;height:56px;border-radius:50%;'
                    f'object-fit:cover;border:2px solid {z_c}33;" onerror="this.style.display=\'none\'">'
                    if headshot else
                    f'<div style="width:56px;height:56px;border-radius:50%;background:#5a8f4e;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-weight:900;font-size:20px;color:#fff;">{d["name"][0]}</div>'
                )
                w   = int(d["wins"])     if pd.notna(d["wins"])     else "—"
                gaa = float(d["gaa"])    if pd.notna(d["gaa"])      else 0.0

                st.html(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                            border-radius:6px;padding:14px;">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                    {img_html}
                    <div>
                      <div style="color:#fff;font-weight:700;font-size:13px;">{d['name']}</div>
                      <div style="color:#8896a8;font-size:10px;">G · {d['team_abbr']}</div>
                      <div style="color:{z_c};font-weight:800;font-size:14px;font-family:monospace;">{z_s}</div>
                    </div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Sv%</div>
                      <div style="color:{sv_c};font-weight:800;font-size:15px;font-family:monospace;">{sv:.2f}%</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Wins</div>
                      <div style="color:#5a8f4e;font-weight:800;font-size:15px;">{w}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">GAA</div>
                      <div style="color:#87ceeb;font-weight:800;font-size:15px;font-family:monospace;">{gaa:.2f}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Sv%/5g</div>
                      <div style="color:#f97316;font-weight:800;font-size:15px;font-family:monospace;">{d['sv_5g']:.2f}%</div>
                    </div>
                  </div>
                  <div style="margin-top:10px;">
                    <a href="/Goalies" target="_self"
                       style="color:#5a8f4e;font-size:10px;text-decoration:underline;
                              text-underline-offset:3px;">View goalie profile →</a>
                  </div>
                </div>
                """)

# ══════════════════════════════════════════════════════════════════════════════
#  TEAMS TAB
# ══════════════════════════════════════════════════════════════════════════════
elif tab == "Teams":
    with st.expander("Filters", expanded=False):
        tc1, tc2 = st.columns([2, 1])
        with tc1:
            t_search = st.text_input("Search", placeholder="Team abbreviation...",
                                     label_visibility="collapsed", key="term_t_search")
        with tc2:
            t_sort = st.selectbox("Sort", [
                "points", "z", "pp_pct", "pk_pct", "sf_g", "diff",
            ], format_func=lambda x: {
                "points": "Points",
                "z":      "Form (σ)",
                "pp_pct": "PP%",
                "pk_pct": "PK%",
                "sf_g":   "SF/g",
                "diff":   "GF-GA",
            }.get(x, x), label_visibility="collapsed", key="term_t_sort")

    t_search = st.session_state.get("term_t_search", "")
    t_sort   = st.session_state.get("term_t_sort", "points")

    @st.cache_data(ttl=900, show_spinner=False)
    def load_teams() -> pd.DataFrame:
        return query("""
            SELECT st.teamAbbrev AS abbr,
                   st.wins, st.losses, st.otLosses, st.gamesPlayed AS gp,
                   st.points,
                   st.goalFor AS gf, st.goalAgainst AS ga,
                   (st.goalFor - st.goalAgainst) AS diff,
                   ROUND(ts.powerPlayPct * 100, 1)  AS pp_pct,
                   ROUND(ts.penaltyKillPct * 100, 1) AS pk_pct,
                   ROUND(ts.shotsForPerGame, 1)      AS sf_g,
                   ROUND(ts.shotsAgainstPerGame, 1)  AS sa_g,
                   ROUND(ts.faceoffWinPct * 100, 1)  AS fo_pct,
                   ROUND(tr.pts_zscore_5v20, 2)      AS z,
                   ROUND(tr.gf_avg_10g, 2)           AS gf10,
                   ROUND(tr.ga_avg_10g, 2)           AS ga10,
                   st.divisionAbbrev                 AS div
            FROM standings st
            LEFT JOIN team_stats ts
                   ON ts.teamFullName = st.teamName AND ts.season = st.season
            LEFT JOIN team_rolling_stats tr
                   ON tr.team_abbr = st.teamAbbrev AND tr.game_recency_rank = 1
            WHERE st.season = (SELECT MAX(season) FROM standings)
            ORDER BY st.points DESC
        """)

    df_t = load_teams()
    if t_search:
        q = t_search.upper()
        df_t = df_t[df_t["abbr"].str.contains(q, na=False)]

    if t_sort in df_t.columns:
        df_t = df_t.sort_values(t_sort, ascending=(t_sort in ("ga", "sa_g")), na_position="last")
    df_t = df_t.reset_index(drop=True)

    col_ttable, col_tdetail = st.columns([3, 1], gap="large")

    with col_ttable:
        st.markdown(
            f"<p style='color:#8896a8;font-size:11px;margin-bottom:6px;'>"
            f"<b style='color:#fff;'>{len(df_t)}</b> teams · current season</p>",
            unsafe_allow_html=True,
        )

        rows_html = ""
        for idx, row in df_t.iterrows():
            diff = int(row["diff"]) if pd.notna(row["diff"]) else 0
            diff_c = "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")
            diff_s = f"+{diff}" if diff > 0 else str(diff)
            z   = float(row["z"]) if pd.notna(row["z"]) else 0.0
            z_c = "#f97316" if z >= 1.0 else ("#5a8f4e" if z >= 0.3 else ("#87ceeb" if z <= -0.3 else "#8896a8"))
            z_s = f"+{z:.2f}" if z >= 0 else f"{z:.2f}"
            pp  = float(row["pp_pct"]) if pd.notna(row["pp_pct"]) else 0.0
            pk  = float(row["pk_pct"]) if pd.notna(row["pk_pct"]) else 0.0
            pp_c = "#f97316" if pp >= 25 else ("#5a8f4e" if pp >= 20 else "#8896a8")
            pk_c = "#f97316" if pk >= 83 else ("#5a8f4e" if pk >= 78 else "#8896a8")
            sf  = f'{row["sf_g"]:.1f}' if pd.notna(row["sf_g"]) else "—"
            sa  = f'{row["sa_g"]:.1f}' if pd.notna(row["sa_g"]) else "—"
            fo  = f'{row["fo_pct"]:.1f}%' if pd.notna(row["fo_pct"]) else "—"
            bg = "rgba(255,255,255,0.015)" if idx % 2 == 0 else "transparent"

            rows_html += (
                f'<tr class="term-row" style="border-bottom:1px solid rgba(255,255,255,0.035);background:{bg};">'
                f'<td style="padding:6px 10px;color:#8896a8;font-family:monospace;font-size:10px;">{idx+1}</td>'
                f'<td style="padding:6px 6px;color:#fff;font-weight:700;font-size:12px;font-family:monospace;">{row["abbr"]}</td>'
                f'<td style="padding:6px 4px;color:#8896a8;font-size:10px;">{row["div"]}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(row["gp"])}</td>'
                f'<td style="padding:6px 6px;color:#5a8f4e;font-weight:700;font-size:11px;text-align:right;">{int(row["wins"])}</td>'
                f'<td style="padding:6px 6px;color:#c41e3a;font-size:11px;text-align:right;">{int(row["losses"])}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:11px;text-align:right;">{int(row["otLosses"])}</td>'
                f'<td style="padding:6px 6px;color:#5a8f4e;font-weight:800;font-size:12px;text-align:right;">{int(row["points"])}</td>'
                f'<td style="padding:6px 6px;color:{diff_c};font-family:monospace;font-size:11px;text-align:right;">{diff_s}</td>'
                f'<td style="padding:6px 6px;color:{pp_c};font-family:monospace;font-size:11px;text-align:right;">{pp:.1f}%</td>'
                f'<td style="padding:6px 6px;color:{pk_c};font-family:monospace;font-size:11px;text-align:right;">{pk:.1f}%</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-family:monospace;font-size:11px;text-align:right;">{sf}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-family:monospace;font-size:11px;text-align:right;">{sa}</td>'
                f'<td style="padding:6px 6px;color:#8896a8;font-size:10px;text-align:right;">{fo}</td>'
                f'<td style="padding:6px 10px;color:{z_c};font-family:monospace;font-weight:800;font-size:12px;text-align:right;">{z_s}σ</td>'
                f'</tr>'
            )

        st.html(
            f'<div style="overflow-x:auto;">'
            f'<table class="term-table" style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:rgba(255,255,255,0.04);border-bottom:2px solid rgba(255,255,255,0.1);">'
            f'<th style="padding:6px 10px;color:#8896a8;font-size:9px;text-align:left;">#</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:left;">TEAM</th>'
            f'<th style="padding:6px 4px;color:#8896a8;font-size:9px;">DIV</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">GP</th>'
            f'<th style="padding:6px 6px;color:#5a8f4e;font-size:9px;text-align:right;">W</th>'
            f'<th style="padding:6px 6px;color:#c41e3a;font-size:9px;text-align:right;">L</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">OTL</th>'
            f'<th style="padding:6px 6px;color:#5a8f4e;font-size:9px;text-align:right;">PTS</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">DIFF</th>'
            f'<th style="padding:6px 6px;color:#f97316;font-size:9px;text-align:right;">PP%</th>'
            f'<th style="padding:6px 6px;color:#87ceeb;font-size:9px;text-align:right;">PK%</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">SF/g</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">SA/g</th>'
            f'<th style="padding:6px 6px;color:#8896a8;font-size:9px;text-align:right;">FO%</th>'
            f'<th style="padding:6px 10px;color:#f97316;font-size:9px;text-align:right;">FORM σ</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
        )

    with col_tdetail:
        st.markdown(
            "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Quick Select</p>",
            unsafe_allow_html=True,
        )
        sel_t_options = {r["abbr"]: r["abbr"] for _, r in df_t.iterrows()}
        if sel_t_options:
            t_chosen = st.selectbox("", list(sel_t_options.keys()),
                                    label_visibility="collapsed", key="term_sel_box_t")
            d = df_t[df_t["abbr"] == t_chosen]
            if not d.empty:
                d   = d.iloc[0]
                z   = float(d["z"]) if pd.notna(d["z"]) else 0.0
                z_c = "#f97316" if z >= 0.5 else ("#87ceeb" if z <= -0.3 else "#8896a8")
                z_s = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"
                pp  = float(d["pp_pct"]) if pd.notna(d["pp_pct"]) else 0.0
                pk  = float(d["pk_pct"]) if pd.notna(d["pk_pct"]) else 0.0
                diff = int(d["diff"]) if pd.notna(d["diff"]) else 0
                diff_c = "#5a8f4e" if diff > 0 else ("#c41e3a" if diff < 0 else "#8896a8")

                # AI insights for team
                df_ti = query_fresh(f"""
                    SELECT headline, insight_type FROM agent_insights
                    WHERE team_abbr = '{d["abbr"]}'
                    ORDER BY generated_at DESC LIMIT 2
                """)

                insights_html = ""
                for _, ins in df_ti.iterrows():
                    insights_html += f"<div style='color:#8896a8;font-size:10px;line-height:1.5;margin-bottom:4px;border-left:2px solid #5a8f4e;padding-left:6px;'>{ins['headline']}</div>"

                st.html(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                            border-radius:6px;padding:14px;">
                  <div style="margin-bottom:12px;">
                    <div style="color:#fff;font-weight:800;font-size:22px;font-family:monospace;">{d['abbr']}</div>
                    <div style="color:{z_c};font-weight:800;font-size:14px;font-family:monospace;">{z_s}</div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px;">
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">Points</div>
                      <div style="color:#5a8f4e;font-weight:800;font-size:16px;">{int(d['points'])}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">W–L–OTL</div>
                      <div style="color:#fff;font-weight:700;font-size:12px;">{int(d['wins'])}–{int(d['losses'])}–{int(d['otLosses'])}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">PP%</div>
                      <div style="color:#f97316;font-weight:800;font-size:15px;font-family:monospace;">{pp:.1f}%</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">PK%</div>
                      <div style="color:#87ceeb;font-weight:800;font-size:15px;font-family:monospace;">{pk:.1f}%</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">GF–GA</div>
                      <div style="color:{diff_c};font-weight:800;font-size:15px;font-family:monospace;">{'+' if diff>0 else ''}{diff}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;">
                      <div style="color:#8896a8;font-size:9px;text-transform:uppercase;">GF/10g</div>
                      <div style="color:#fff;font-weight:700;font-size:15px;">{float(d['gf10']):.2f}</div>
                    </div>
                  </div>
                  {f'<div style="margin-top:4px;"><div style="color:#5a8f4e;font-size:9px;text-transform:uppercase;margin-bottom:4px;">AI Insights</div>{insights_html}</div>' if insights_html else ''}
                  <div style="margin-top:10px;">
                    <a href="/Teams" target="_self"
                       style="color:#5a8f4e;font-size:10px;text-decoration:underline;
                              text-underline-offset:3px;">View team dashboard →</a>
                  </div>
                </div>
                """)

# ── Legend ─────────────────────────────────────────────────────────────────────
st.markdown(
    """<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;padding-top:12px;
                  border-top:1px solid rgba(255,255,255,0.06);">
      <span style="color:#f97316;font-size:10px;">■ Hot (σ ≥ 1.5)</span>
      <span style="color:#5a8f4e;font-size:10px;">■ Above avg (σ ≥ 0.5)</span>
      <span style="color:#8896a8;font-size:10px;">■ Neutral</span>
      <span style="color:#87ceeb;font-size:10px;">■ Below avg (σ ≤ −0.5)</span>
      <span style="color:#3b82f6;font-size:10px;">■ Cold (σ ≤ −1.5)</span>
      <span style="color:#8896a8;font-size:10px;margin-left:8px;">σ = z-score vs 20-game baseline</span>
    </div>""",
    unsafe_allow_html=True,
)

data_source_footer()
