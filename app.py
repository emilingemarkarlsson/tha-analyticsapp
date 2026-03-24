"""THA Analytics – NHL Hockey Intelligence (Streamlit entry point)."""
import streamlit as st

st.set_page_config(
    page_title="THA Analytics",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Hide default Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #050505;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* Card-like containers */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 6px;
        background: rgba(255,255,255,0.03);
    }

    /* Tables */
    thead tr th {
        background: rgba(255,255,255,0.04) !important;
        color: #8896a8 !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
    }

    /* Metric labels */
    [data-testid="stMetricLabel"] { color: #8896a8 !important; font-size: 11px !important; }
    [data-testid="stMetricValue"] { font-weight: 800 !important; letter-spacing: -0.02em; }

    /* Input fields */
    input, textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 4px !important;
        color: #f1f5f9 !important;
    }

    /* Buttons */
    div[data-testid="stButton"] button {
        background: #5a8f4e !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 4px !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar branding ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 8px 0 20px 0;">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="background:#5a8f4e; color:#fff; font-weight:900;
                        font-size:11px; padding:4px 7px; border-radius:4px;
                        letter-spacing:0.05em;">THA</div>
            <div>
              <div style="color:#fff; font-weight:700; font-size:14px;
                          letter-spacing:-0.01em; line-height:1.1;">Analytics</div>
              <div style="color:#8896a8; font-size:11px;">NHL Intelligence</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.page_link("app.py", label="Intelligence Feed", icon=":material/trending_up:")
    st.page_link("pages/2_Standings.py", label="Standings", icon=":material/leaderboard:")
    st.page_link("pages/3_Players.py", label="Players", icon=":material/person:")
    st.page_link("pages/4_Teams.py", label="Teams", icon=":material/shield:")
    st.page_link("pages/5_Chat.py", label="AI Chat", icon=":material/chat:")

    st.markdown("<hr style='border-color:rgba(255,255,255,0.08);margin:20px 0;'>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08);
                    border-radius:5px; padding:10px 12px;">
          <div style="display:flex; align-items:center; gap:6px; margin-bottom:5px;">
            <span style="width:7px;height:7px;border-radius:50%;background:#5a8f4e;display:inline-block;"></span>
            <span style="color:#5a8f4e; font-size:11px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;">Live</span>
          </div>
          <div style="color:#8896a8; font-size:11px; line-height:1.5;">
            16 seasons · 850K+ records<br>Updated daily 09:00 CET
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Default page = Intelligence Feed ─────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from lib.db import query

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

st.markdown(
    "<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;margin-bottom:4px;'>Intelligence Feed</h1>",
    unsafe_allow_html=True,
)

try:
    df_insights = query("""
        SELECT insight_type, entity_name, team_abbr, zscore, severity,
               headline, body, game_date, generated_at
        FROM agent_insights
        ORDER BY generated_at DESC, ABS(zscore) DESC
        LIMIT 25
    """)
    df_hot = query("""
        SELECT player_first_name || ' ' || player_last_name AS name,
               CAST(player_id AS VARCHAR) AS player_id,
               team_abbr, pts_avg_5g, pts_zscore_5v20
        FROM player_rolling_stats
        WHERE game_recency_rank = 1
          AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
          AND gp_season >= 20
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
        ORDER BY pts_zscore_5v20 ASC LIMIT 5
    """)
    db_ok = True
except Exception as e:
    st.error(f"Database error: {e}")
    df_insights = df_hot = df_cold = None
    db_ok = False

if db_ok:
    latest_date = str(df_insights["game_date"].iloc[0])[:10] if not df_insights.empty else "—"
    st.markdown(
        f"<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>"
        f"AI-generated anomaly detection across 16 seasons of NHL data "
        f"&nbsp;·&nbsp; Last update: <span style='color:#f1f5f9;'>{latest_date}</span></p>",
        unsafe_allow_html=True,
    )

    col_feed, col_side = st.columns([2, 1], gap="large")

    with col_feed:
        st.markdown(
            "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:12px;'>Latest Insights</p>",
            unsafe_allow_html=True,
        )
        if df_insights.empty:
            st.info("No insights yet — pipeline runs daily at 09:00 CET.")
        else:
            for _, row in df_insights.iterrows():
                color = INSIGHT_COLORS.get(row["insight_type"], "#5a8f4e")
                label = INSIGHT_LABELS.get(row["insight_type"], row["insight_type"])
                z = float(row["zscore"])
                z_color = "#f97316" if z >= 0 else "#87ceeb"
                z_str = f"+{z:.2f}σ" if z >= 0 else f"{z:.2f}σ"
                sev = int(row["severity"]) if row["severity"] else 0
                dots = "".join(
                    f"<span style='display:inline-block;width:6px;height:6px;border-radius:50%;"
                    f"background:{'  ' + color if i < sev else 'rgba(255,255,255,0.12)'};"
                    f"margin-left:2px;'></span>"
                    for i in range(1, 6)
                )
                game_date = str(row["game_date"])[:10]
                st.markdown(
                    f"""
                    <div style="border-left:2px solid {color};background:rgba(255,255,255,0.03);
                                border-radius:0 5px 5px 0;padding:12px 16px;margin-bottom:8px;
                                border-top:1px solid rgba(255,255,255,0.06);
                                border-right:1px solid rgba(255,255,255,0.06);
                                border-bottom:1px solid rgba(255,255,255,0.06);">
                      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
                        <div>
                          <span style="color:#fff;font-weight:600;font-size:13px;">{row['entity_name']}</span>
                          <span style="background:rgba(255,255,255,0.07);color:#8896a8;font-size:10px;
                                       padding:1px 6px;border-radius:3px;margin-left:6px;font-family:monospace;">{row['team_abbr']}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:10px;">
                          <span style="color:{color};font-size:11px;background:rgba(255,255,255,0.05);
                                       padding:2px 7px;border-radius:3px;">{label}</span>
                          <span style="color:{z_color};font-size:12px;font-family:monospace;font-weight:700;">{z_str}</span>
                        </div>
                      </div>
                      {"<p style='color:#fff;font-size:13px;font-weight:500;margin:8px 0 4px;line-height:1.4;'>" + str(row['headline']) + "</p>" if row['headline'] else ""}
                      {"<p style='color:#8896a8;font-size:12px;line-height:1.5;margin:0;'>" + str(row['body']) + "</p>" if row['body'] else ""}
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                        <span style="color:rgba(255,255,255,0.2);font-size:11px;">{game_date}</span>
                        <span>{dots}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col_side:
        st.markdown(
            "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:10px;'>Hottest Right Now</p>",
            unsafe_allow_html=True,
        )
        for _, p in df_hot.iterrows():
            z = float(p["pts_zscore_5v20"])
            st.markdown(
                f"""<div style="display:flex;justify-content:space-between;align-items:center;
                              padding:7px 12px;border-bottom:1px solid rgba(255,255,255,0.05);">
                  <div>
                    <div style="color:#fff;font-size:12px;font-weight:500;">{p['name']}</div>
                    <div style="color:#8896a8;font-size:11px;">{p['team_abbr']}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="color:#f97316;font-family:monospace;font-size:12px;font-weight:700;">+{z:.2f}σ</div>
                    <div style="color:#8896a8;font-size:11px;">{float(p['pts_avg_5g']):.2f} pts/g</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        st.markdown(
            "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#8896a8;margin-bottom:10px;'>Slumping</p>",
            unsafe_allow_html=True,
        )
        for _, p in df_cold.iterrows():
            z = float(p["pts_zscore_5v20"])
            st.markdown(
                f"""<div style="display:flex;justify-content:space-between;align-items:center;
                              padding:7px 12px;border-bottom:1px solid rgba(255,255,255,0.05);">
                  <div>
                    <div style="color:#fff;font-size:12px;font-weight:500;">{p['name']}</div>
                    <div style="color:#8896a8;font-size:11px;">{p['team_abbr']}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="color:#87ceeb;font-family:monospace;font-size:12px;font-weight:700;">{z:.2f}σ</div>
                    <div style="color:#8896a8;font-size:11px;">{float(p['pts_avg_5g']):.2f} pts/g</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                          border-radius:5px;padding:12px 14px;">
              <p style="color:#5a8f4e;font-size:10px;font-weight:600;text-transform:uppercase;
                         letter-spacing:0.08em;margin-bottom:6px;">Methodology</p>
              <p style="color:#8896a8;font-size:11px;line-height:1.6;margin:0;">
                Z-scores compare a player's last 5 games against their 20-game rolling baseline.
                Anomalies beyond ±1.5σ trigger an insight.
              </p>
            </div>""",
            unsafe_allow_html=True,
        )
