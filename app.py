"""THA Analytics – NHL Hockey Intelligence (Streamlit entry point)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

st.set_page_config(
    page_title="THA Analytics",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded",
)

from lib.sidebar import render as _render_sidebar
_render_sidebar()

from lib.db import query, get_data_date
from lib.components import data_source_footer, zscore_legend

INSIGHT_COLORS: dict[str, str] = {
    "hot_streak": "#f97316",
    "breakout": "#5a8f4e",
    "cold_spell": "#87ceeb",
    "slump": "#8896a8",
    "goalie_hot": "#5a8f4e",
    "goalie_cold": "#87ceeb",
    "team_surge": "#f97316",
    "team_collapse": "#c41e3a",
    "possession_edge": "#87ceeb",
}
INSIGHT_LABELS: dict[str, str] = {
    "hot_streak": "Hot Streak", "breakout": "Breakout", "cold_spell": "Cold Spell",
    "slump": "Slump", "goalie_hot": "Goalie Hot", "goalie_cold": "Goalie Cold",
    "team_surge": "Team Surge", "team_collapse": "Team Collapse", "possession_edge": "Possession Edge",
}
FILTER_GROUPS: dict[str, list[str]] = {
    "All":     [],
    "Hot":     ["hot_streak", "breakout", "goalie_hot", "team_surge"],
    "Cold":    ["cold_spell", "slump", "goalie_cold", "team_collapse"],
    "Goalies": ["goalie_hot", "goalie_cold"],
}

from lib.components import page_header
page_header("Intelligence Feed", "AI-generated insights · updated daily", data_date=get_data_date())

try:
    df_insights = query("""
        SELECT insight_type, entity_name, team_abbr, zscore, severity,
               headline, body, game_date, generated_at
        FROM agent_insights
        ORDER BY generated_at DESC, ABS(zscore) DESC
        LIMIT 50
    """)
    df_hot = query("""
        SELECT player_first_name || ' ' || player_last_name AS name,
               CAST(player_id AS VARCHAR) AS player_id,
               team_abbr, pts_avg_5g, pts_zscore_5v20
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND gp_season >= 20
          AND player_first_name IS NOT NULL
          AND player_last_name IS NOT NULL
        ORDER BY pts_zscore_5v20 DESC LIMIT 8
    """)
    df_cold = query("""
        SELECT player_first_name || ' ' || player_last_name AS name,
               CAST(player_id AS VARCHAR) AS player_id,
               team_abbr, pts_avg_5g, pts_zscore_5v20
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND gp_season >= 20
          AND player_first_name IS NOT NULL
          AND player_last_name IS NOT NULL
        ORDER BY pts_zscore_5v20 ASC LIMIT 5
    """)
    db_ok = True
except Exception as e:
    st.error(f"Database error: {e}")
    df_insights = df_hot = df_cold = None
    db_ok = False

if db_ok:
    latest_date = str(df_insights["game_date"].iloc[0])[:10] if not df_insights.empty else "—"

    # ── Summary bar ───────────────────────────────────────────────────────────
    n_total = len(df_insights)
    n_hot   = int(df_insights["insight_type"].isin(FILTER_GROUPS["Hot"]).sum())
    n_cold  = int(df_insights["insight_type"].isin(FILTER_GROUPS["Cold"]).sum())
    st.markdown(
        f"""<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                      border-radius:5px;padding:8px 16px;display:flex;align-items:center;gap:10px;">
            <span style="color:#8896a8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;">Insights</span>
            <span style="color:#fff;font-weight:700;font-size:16px;">{n_total}</span>
          </div>
          <div style="background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.2);
                      border-radius:5px;padding:8px 16px;display:flex;align-items:center;gap:10px;">
            <span style="color:#8896a8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;">Hot</span>
            <span style="color:#f97316;font-weight:700;font-size:16px;">{n_hot}</span>
          </div>
          <div style="background:rgba(135,206,235,0.06);border:1px solid rgba(135,206,235,0.18);
                      border-radius:5px;padding:8px 16px;display:flex;align-items:center;gap:10px;">
            <span style="color:#8896a8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;">Cold</span>
            <span style="color:#87ceeb;font-weight:700;font-size:16px;">{n_cold}</span>
          </div>
          <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                      border-radius:5px;padding:8px 16px;display:flex;align-items:center;gap:10px;">
            <span style="color:#8896a8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;">Updated</span>
            <span style="color:#f1f5f9;font-weight:600;font-size:13px;font-family:monospace;">{latest_date}</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    col_feed, col_side = st.columns([2, 1], gap="large")

    with col_feed:
        # Filter pills
        if "insight_filter" not in st.session_state:
            st.session_state.insight_filter = "All"

        pill_cols = st.columns(len(FILTER_GROUPS))
        for i, label in enumerate(FILTER_GROUPS):
            active = st.session_state.insight_filter == label
            bg = "#5a8f4e" if active else "rgba(255,255,255,0.05)"
            fg = "#fff" if active else "#8896a8"
            border = "#5a8f4e" if active else "rgba(255,255,255,0.1)"
            with pill_cols[i]:
                if st.button(label, key=f"filter_{label}", use_container_width=True):
                    st.session_state.insight_filter = label
                    st.rerun()

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # Apply filter
        active_filter = st.session_state.insight_filter
        types = FILTER_GROUPS[active_filter]
        filtered = df_insights[df_insights["insight_type"].isin(types)] if types else df_insights

        if filtered.empty:
            st.info("No insights for this filter.")
        else:
            for _, row in filtered.iterrows():
                color = INSIGHT_COLORS.get(row["insight_type"], "#5a8f4e")
                label = INSIGHT_LABELS.get(row["insight_type"], row["insight_type"])
                z = float(row["zscore"])
                z_color = "#f97316" if z >= 0 else "#87ceeb"
                z_str = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"
                sev = int(row["severity"]) if row["severity"] else 0
                dots = "".join(
                    f"<span style='display:inline-block;width:6px;height:6px;border-radius:50%;"
                    f"background:{color if i < sev else 'rgba(255,255,255,0.12)'};"
                    f"margin-left:2px;'></span>"
                    for i in range(1, 6)
                )
                game_date = str(row["game_date"])[:10]
                headline = str(row["headline"]) if row["headline"] else ""
                body = str(row["body"]) if row["body"] else ""
                st.markdown(
                    f"""<div style="border-left:2px solid {color};background:rgba(255,255,255,0.03);
                                border-radius:0 5px 5px 0;padding:12px 16px;margin-bottom:8px;
                                border-top:1px solid rgba(255,255,255,0.06);
                                border-right:1px solid rgba(255,255,255,0.06);
                                border-bottom:1px solid rgba(255,255,255,0.06);">
                      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                        <div style="display:flex;align-items:center;gap:8px;">
                          <span style="color:#fff;font-weight:700;font-size:13px;">{row['entity_name']}</span>
                          <span style="background:rgba(255,255,255,0.07);color:#8896a8;font-size:10px;
                                       padding:1px 6px;border-radius:3px;font-family:monospace;">{row['team_abbr']}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                          <span style="color:{color};font-size:10px;font-weight:600;text-transform:uppercase;
                                       letter-spacing:0.05em;background:rgba(255,255,255,0.04);
                                       padding:2px 8px;border-radius:3px;border:1px solid {color}33;">{label}</span>
                          <span style="color:{z_color};font-size:13px;font-family:monospace;font-weight:800;min-width:56px;text-align:right;">{z_str}</span>
                        </div>
                      </div>
                      {"<p style='color:#fff;font-size:12px;font-weight:600;margin:8px 0 3px;line-height:1.4;'>" + headline + "</p>" if headline else ""}
                      {"<p style='color:#8896a8;font-size:11px;line-height:1.55;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;'>" + body + "</p>" if body else ""}
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;">
                        <span style="color:rgba(255,255,255,0.2);font-size:11px;font-family:monospace;">{game_date}</span>
                        <span>{dots}</span>
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    with col_side:
        # Hot section
        st.markdown(
            """<div style="background:rgba(249,115,22,0.06);border:1px solid rgba(249,115,22,0.18);
                           border-radius:5px 5px 0 0;padding:8px 14px;">
                 <span style="color:#f97316;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Hottest Right Now</span>
               </div>""",
            unsafe_allow_html=True,
        )
        rows_hot = ""
        for _, p in df_hot.iterrows():
            z = float(p["pts_zscore_5v20"])
            rows_hot += f"""<div style="display:flex;justify-content:space-between;align-items:center;
                              padding:8px 14px;border-bottom:1px solid rgba(255,255,255,0.04);">
              <div>
                <div style="color:#fff;font-size:12px;font-weight:500;">{p['name']}</div>
                <div style="color:#8896a8;font-size:11px;">{p['team_abbr']}</div>
              </div>
              <div style="text-align:right;">
                <div style="color:#f97316;font-family:monospace;font-size:12px;font-weight:700;">+{z:.2f}σ</div>
                <div style="color:#8896a8;font-size:11px;">{float(p['pts_avg_5g']):.2f} pts/g</div>
              </div>
            </div>"""
        st.markdown(
            f"""<div style="border:1px solid rgba(249,115,22,0.18);border-top:none;
                            border-radius:0 0 5px 5px;overflow:hidden;margin-bottom:16px;">{rows_hot}</div>""",
            unsafe_allow_html=True,
        )

        # Cold section
        st.markdown(
            """<div style="background:rgba(135,206,235,0.05);border:1px solid rgba(135,206,235,0.15);
                           border-radius:5px 5px 0 0;padding:8px 14px;">
                 <span style="color:#87ceeb;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Slumping</span>
               </div>""",
            unsafe_allow_html=True,
        )
        rows_cold = ""
        for _, p in df_cold.iterrows():
            z = float(p["pts_zscore_5v20"])
            rows_cold += f"""<div style="display:flex;justify-content:space-between;align-items:center;
                              padding:8px 14px;border-bottom:1px solid rgba(255,255,255,0.04);">
              <div>
                <div style="color:#fff;font-size:12px;font-weight:500;">{p['name']}</div>
                <div style="color:#8896a8;font-size:11px;">{p['team_abbr']}</div>
              </div>
              <div style="text-align:right;">
                <div style="color:#87ceeb;font-family:monospace;font-size:12px;font-weight:700;">{z:.2f}σ</div>
                <div style="color:#8896a8;font-size:11px;">{float(p['pts_avg_5g']):.2f} pts/g</div>
              </div>
            </div>"""
        st.markdown(
            f"""<div style="border:1px solid rgba(135,206,235,0.15);border-top:none;
                            border-radius:0 0 5px 5px;overflow:hidden;margin-bottom:16px;">{rows_cold}</div>""",
            unsafe_allow_html=True,
        )

        # Methodology card
        st.markdown(
            """<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);
                          border-radius:5px;padding:12px 14px;">
              <p style="color:#5a8f4e;font-size:10px;font-weight:600;text-transform:uppercase;
                         letter-spacing:0.08em;margin-bottom:6px;">Methodology</p>
              <p style="color:#8896a8;font-size:11px;line-height:1.6;margin:0;">
                Z-scores compare a player's last 5 games against their 20-game rolling baseline.
                Anomalies beyond ±0.8σ trigger an insight.
              </p>
            </div>""",
            unsafe_allow_html=True,
        )

data_source_footer()
zscore_legend()
