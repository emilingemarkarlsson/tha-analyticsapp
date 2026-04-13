"""Shared sidebar and global CSS – call render() on every page."""
import streamlit as st


def render() -> None:
    """Inject global CSS and render sidebar navigation."""

    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        [data-testid="stSidebarNav"] { display: none !important; }

        /* ── Force sidebar always visible ─────────────────── */
        section[data-testid="stSidebar"] {
            transform: translateX(0px) !important;
            min-width: 244px !important;
            width: 244px !important;
            visibility: visible !important;
            display: flex !important;
            background: #050505;
            border-right: 1px solid rgba(255,255,255,0.08);
        }
        /* Hide the collapse arrow – sidebar is always open */
        [data-testid="collapsedControl"] { display: none !important; }

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

        /* Primary buttons – THA green */
        div[data-testid="stButton"] button[kind="primary"] {
            background: #5a8f4e !important;
            color: #fff !important;
            border: 1px solid #5a8f4e !important;
            font-weight: 700 !important;
            border-radius: 4px !important;
        }
        /* Secondary buttons – muted/inactive */
        div[data-testid="stButton"] button[kind="secondary"] {
            background: rgba(255,255,255,0.04) !important;
            color: #8896a8 !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            font-weight: 500 !important;
            border-radius: 4px !important;
        }
        div[data-testid="stButton"] button[kind="secondary"]:hover {
            background: rgba(255,255,255,0.09) !important;
            color: #f1f5f9 !important;
            border-color: rgba(255,255,255,0.18) !important;
        }

        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }


        /* ── Mobile responsiveness ──────────────────────── */
        @media (max-width: 768px) {
            /* Stack all column pairs on mobile */
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }

            /* Reduce main content padding on mobile */
            [data-testid="block-container"] {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1rem !important;
            }

            /* Make metric cards readable on mobile */
            [data-testid="stMetricValue"] {
                font-size: 1.4rem !important;
            }

            /* Shrink page header font on mobile */
            h1 { font-size: 1.4rem !important; }
            h2 { font-size: 1.1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Favicon (SVG THA orange box) ───────────────────────────────────────────
    st.markdown(
        """<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32'%3E%3Crect width='32' height='32' rx='4' fill='%23f97316'/%3E%3Ctext x='16' y='22' font-family='Arial,sans-serif' font-size='13' font-weight='900' fill='white' text-anchor='middle'%3ETHA%3C/text%3E%3C/svg%3E">""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        # ── Logo ──────────────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="margin-top:-24px; padding-bottom:24px; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:16px;">
              <div style="display:flex; align-items:center; gap:9px;">
                <div style="background:#5a8f4e; border-radius:5px; width:30px; height:30px;
                            display:flex; align-items:center; justify-content:center;
                            font-family:Arial,sans-serif; font-size:11px; font-weight:900;
                            color:#fff; letter-spacing:-0.02em; flex-shrink:0;">THA</div>
                <div>
                  <div style="color:#fff; font-weight:800; font-size:15px;
                              letter-spacing:-0.03em; line-height:1.1;">The Hockey Analytics</div>
                  <div style="color:#5a8f4e; font-size:10px; font-weight:600;
                              letter-spacing:0.06em; text-transform:uppercase; margin-top:1px;">NHL · Analytics</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Nav group: Analytics ───────────────────────────────────────────────
        st.markdown(
            "<p style='color:rgba(255,255,255,0.25);font-size:9px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.12em;padding:0 4px;"
            "margin-bottom:2px;'>Analytics</p>",
            unsafe_allow_html=True,
        )
        st.page_link("app.py",               label="Intelligence Feed", icon=":material/trending_up:")
        st.page_link("pages/1_Deep_Dive.py", label="Deep Dive",         icon=":material/analytics:")
        st.page_link("pages/2_Standings.py", label="Standings",         icon=":material/leaderboard:")
        st.page_link("pages/3_Players.py",   label="Players",           icon=":material/people:")
        st.page_link("pages/4_Teams.py",     label="Teams",             icon=":material/groups:")

        # ── Nav group: Explore ─────────────────────────────────────────────────
        st.markdown(
            "<p style='color:rgba(255,255,255,0.25);font-size:9px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.12em;padding:0 4px;"
            "margin:10px 0 2px;'>Explore</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/8_Player_History.py", label="Player History", icon=":material/person_search:")
        st.page_link("pages/11_Goalies.py",        label="Goalies",        icon=":material/sports_hockey:")
        st.page_link("pages/12_Playoffs.py",       label="Playoffs",       icon=":material/emoji_events:")

        # ── Nav group: Tools ───────────────────────────────────────────────────
        st.markdown(
            "<p style='color:rgba(255,255,255,0.25);font-size:9px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.12em;padding:0 4px;"
            "margin:10px 0 2px;'>Tools</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/6_Screener.py",   label="Player Finder", icon=":material/filter_list:")
        st.page_link("pages/7_Watchlist.py",  label="Watchlist",     icon=":material/bookmark:")
        st.page_link("pages/5_Chat.py",        label="Ask AI",        icon=":material/chat:")
        st.page_link("pages/13_Compare.py",    label="Compare",       icon=":material/compare_arrows:")

        # ── Nav group: Account ─────────────────────────────────────────────────
        st.markdown(
            "<p style='color:rgba(255,255,255,0.25);font-size:9px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.12em;padding:0 4px;"
            "margin:10px 0 2px;'>Account</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/10_Account.py", label="My Account", icon=":material/manage_accounts:")

        st.markdown(
            "<hr style='border-color:rgba(255,255,255,0.08);margin:16px 0;'>",
            unsafe_allow_html=True,
        )

        # ── Logged-in user chip ────────────────────────────────────────────────
        from lib.auth import get_user
        user = get_user()
        if user:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:12px;'>"
                f"<div style='background:#5a8f4e;border-radius:50%;width:22px;height:22px;"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-size:10px;font-weight:800;color:#fff;flex-shrink:0;'>"
                f"{user['email'][0].upper()}</div>"
                f"<span style='color:#8896a8;font-size:11px;overflow:hidden;"
                f"text-overflow:ellipsis;white-space:nowrap;'>{user['email']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Data status widget ─────────────────────────────────────────────────
        try:
            from lib.db import get_data_date
            data_date = get_data_date()
        except Exception:
            data_date = "—"

        status_color = "#5a8f4e" if data_date != "—" else "#f97316"
        st.markdown(
            f"""
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08);
                        border-radius:5px; padding:10px 12px;">
              <div style="display:flex; align-items:center; justify-content:space-between;
                          margin-bottom:6px;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="width:7px;height:7px;border-radius:50%;background:{status_color};
                               display:inline-block;"></span>
                  <span style="color:{status_color}; font-size:11px; font-weight:600;
                               letter-spacing:0.06em; text-transform:uppercase;">Live</span>
                </div>
                <span style="color:#8896a8;font-size:10px;font-family:monospace;">{data_date}</span>
              </div>
              <div style="color:#8896a8; font-size:11px; line-height:1.5;">
                16 seasons · 850K+ records<br>
                <span style="color:rgba(255,255,255,0.3);font-size:10px;">
                  Updated daily · NHL Stats API
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Feedback & Support ─────────────────────────────────────────────────
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        with st.expander("Feedback & Support", icon=":material/feedback:"):
            from lib.feedback import send_feedback
            from lib.auth import get_user as _get_user
            _u = _get_user()

            kind = st.selectbox(
                "Type",
                ["Feedback", "Bug report", "Question"],
                label_visibility="collapsed",
                key="fb_kind",
            )
            msg = st.text_area(
                "Message",
                placeholder="Write your message here…",
                height=100,
                label_visibility="collapsed",
                key="fb_msg",
            )
            if st.button("Send", use_container_width=True, key="fb_send"):
                if not msg.strip():
                    st.warning("Please write a message first.")
                else:
                    ok, err = send_feedback(
                        kind=kind,
                        message=msg.strip(),
                        user_email=_u["email"] if _u else "",
                    )
                    if ok:
                        st.success("Sent! We'll get back to you soon.")
                        st.session_state["fb_msg"] = ""
                    else:
                        st.error(f"Could not send: {err}")
