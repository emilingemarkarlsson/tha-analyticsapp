"""Shared sidebar and global CSS – call render() on every page."""
import streamlit as st


def render() -> None:
    """Inject global CSS and render sidebar navigation."""
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        [data-testid="stSidebarNav"] { display: none !important; }

        section[data-testid="stSidebar"] {
            background: #050505;
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: 6px;
            background: rgba(255,255,255,0.03);
        }

        thead tr th {
            background: rgba(255,255,255,0.04) !important;
            color: #8896a8 !important;
            font-size: 11px !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 600;
        }

        [data-testid="stMetricLabel"] { color: #8896a8 !important; font-size: 11px !important; }
        [data-testid="stMetricValue"] { font-weight: 800 !important; letter-spacing: -0.02em; }

        input, textarea {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            border-radius: 4px !important;
            color: #f1f5f9 !important;
        }

        div[data-testid="stButton"] button {
            background: #5a8f4e !important;
            color: white !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 4px !important;
        }

        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

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
        st.page_link("pages/6_Screener.py", label="Screener", icon=":material/filter_list:")
        st.page_link("pages/7_Watchlist.py", label="My Hockey Room", icon=":material/folder_special:")
        st.page_link("pages/8_Player_History.py", label="Player History", icon=":material/show_chart:")

        st.markdown(
            "<hr style='border-color:rgba(255,255,255,0.08);margin:20px 0;'>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08);
                        border-radius:5px; padding:10px 12px;">
              <div style="display:flex; align-items:center; gap:6px; margin-bottom:5px;">
                <span style="width:7px;height:7px;border-radius:50%;background:#5a8f4e;
                             display:inline-block;"></span>
                <span style="color:#5a8f4e; font-size:11px; font-weight:600;
                             letter-spacing:0.06em; text-transform:uppercase;">Live</span>
              </div>
              <div style="color:#8896a8; font-size:11px; line-height:1.5;">
                16 seasons · 850K+ records<br>Updated daily 09:00 CET
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
