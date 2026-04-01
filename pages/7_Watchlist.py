"""Watchlist & Roster Builder – manage players and build lineups."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from lib.db import query_fresh
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib import userdb

st.set_page_config(page_title="Watchlist – THA Analytics", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
require_login()

st.markdown(
    "<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;margin-bottom:4px;'>My Hockey Room</h1>"
    "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>Watchlist · Roster Builder · Player comparison</p>",
    unsafe_allow_html=True,
)

tab_watch, tab_roster = st.tabs(["Watchlist", "Roster Builder"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_watch:
    watched = userdb.watchlist_all()

    if not watched:
        st.info("Your watchlist is empty. Use the Screener to add players.")
    else:
        player_ids = [p["player_id"] for p in watched]
        ids_sql = "','".join(player_ids)

        try:
            df_live = query_fresh(f"""
                SELECT CAST(player_id AS VARCHAR) AS player_id,
                       player_first_name || ' ' || player_last_name AS name,
                       team_abbr, position,
                       gp_season, goals_season, assists_season, pts_season,
                       ROUND(pts_avg_5g, 2)       AS pts_avg_5g,
                       ROUND(pts_avg_20g, 2)       AS pts_avg_20g,
                       ROUND(toi_avg_10g / 60, 1)  AS toi_min,
                       ROUND(pts_zscore_5v20, 2)   AS pts_zscore_5v20
                FROM player_rolling_stats
                WHERE game_recency_rank = 1
                  AND CAST(player_id AS VARCHAR) IN ('{ids_sql}')
            """)
        except Exception as e:
            st.error(f"Database error: {e}")
            df_live = pd.DataFrame()

        # Merge saved note + live stats
        saved_map = {p["player_id"]: p for p in watched}

        # Header action row
        hcol1, hcol2 = st.columns([3, 1])
        with hcol1:
            st.markdown(
                f"<p style='color:#8896a8;font-size:12px;margin-bottom:12px;'>"
                f"<span style='color:#fff;font-weight:700;'>{len(watched)}</span> players watched</p>",
                unsafe_allow_html=True,
            )
        with hcol2:
            remove_sel = st.selectbox(
                "", ["— remove player —"] + [p["player_name"] for p in watched],
                label_visibility="collapsed", key="wl_remove_sel",
            )
            if remove_sel != "— remove player —":
                pid_to_remove = next(
                    (p["player_id"] for p in watched if p["player_name"] == remove_sel), None
                )
                if pid_to_remove and st.button("Remove", key="btn_wl_remove"):
                    userdb.watchlist_remove(pid_to_remove)
                    st.rerun()

        # ── Player cards ──────────────────────────────────────────────────────
        for p in watched:
            pid = p["player_id"]
            live = df_live[df_live["player_id"] == pid]
            if live.empty:
                continue
            r = live.iloc[0]
            z = float(r["pts_zscore_5v20"])
            z_color = "#f97316" if z >= 1.0 else ("#5a8f4e" if z >= 0.5 else ("#87ceeb" if z <= -0.8 else "#8896a8"))
            z_str = f"{z:+.2f}σ"
            note = p.get("note", "")

            with st.container():
                c_info, c_stats, c_form, c_actions = st.columns([3, 3, 1, 2])

                with c_info:
                    st.markdown(
                        f"<div style='padding:10px 0;'>"
                        f"<div style='color:#fff;font-weight:700;font-size:14px;'>{r['name']}</div>"
                        f"<div style='color:#8896a8;font-size:12px;'>{r['team_abbr']} · {r['position']} · {int(r['gp_season'])} GP</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with c_stats:
                    st.markdown(
                        f"<div style='padding:10px 0;display:flex;gap:16px;'>"
                        f"<div><div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>G</div>"
                        f"<div style='color:#fff;font-weight:700;font-size:15px;'>{int(r['goals_season'])}</div></div>"
                        f"<div><div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>A</div>"
                        f"<div style='color:#fff;font-weight:700;font-size:15px;'>{int(r['assists_season'])}</div></div>"
                        f"<div><div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>PTS</div>"
                        f"<div style='color:#5a8f4e;font-weight:800;font-size:15px;'>{int(r['pts_season'])}</div></div>"
                        f"<div><div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>PTS/5g</div>"
                        f"<div style='color:#fff;font-size:14px;'>{r['pts_avg_5g']}</div></div>"
                        f"<div><div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>TOI</div>"
                        f"<div style='color:#8896a8;font-size:14px;'>{r['toi_min']}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with c_form:
                    st.markdown(
                        f"<div style='padding:14px 0;text-align:center;'>"
                        f"<div style='color:#8896a8;font-size:10px;text-transform:uppercase;'>Form</div>"
                        f"<div style='color:{z_color};font-weight:800;font-family:monospace;font-size:16px;'>{z_str}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with c_actions:
                    # Note input
                    new_note = st.text_input(
                        "Note", value=note, placeholder="Add note...",
                        key=f"note_{pid}", label_visibility="collapsed",
                    )
                    if new_note != note:
                        userdb.watchlist_note(pid, new_note)

                    # Find replacement
                    if st.button("Find replacement", key=f"replace_{pid}", use_container_width=True):
                        st.session_state["find_replace_pid"] = pid
                        st.session_state["find_replace_name"] = r["name"]
                        st.session_state["find_replace_pos"] = r["position"]
                        st.session_state["find_replace_pts20"] = float(r["pts_avg_20g"])

                st.markdown(
                    "<div style='border-bottom:1px solid rgba(255,255,255,0.06);margin:0;'></div>",
                    unsafe_allow_html=True,
                )

        # ── Replacement suggestions panel ─────────────────────────────────────
        if "find_replace_pid" in st.session_state:
            rname = st.session_state["find_replace_name"]
            rpos  = st.session_state["find_replace_pos"]
            rpts  = st.session_state["find_replace_pts20"]

            st.markdown(
                f"<div style='margin-top:24px;padding:14px 16px;"
                f"background:rgba(90,143,78,0.06);border:1px solid rgba(90,143,78,0.25);"
                f"border-radius:6px;'>"
                f"<p style='color:#5a8f4e;font-size:11px;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:0.08em;margin-bottom:6px;'>Replacement candidates for {rname}</p>"
                f"<p style='color:#8896a8;font-size:11px;margin:0;'>"
                f"Same position ({rpos}) · similar 20g baseline (±40%) · sorted by form</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

            low, high = rpts * 0.6, rpts * 1.4
            rpid = st.session_state["find_replace_pid"]
            try:
                df_rep = query_fresh(f"""
                    SELECT CAST(player_id AS VARCHAR) AS player_id,
                           player_first_name || ' ' || player_last_name AS name,
                           team_abbr,
                           gp_season,
                           ROUND(pts_avg_20g, 2)      AS pts_avg_20g,
                           ROUND(pts_avg_5g, 2)        AS pts_avg_5g,
                           ROUND(toi_avg_10g / 60, 1)  AS toi_min,
                           ROUND(pts_zscore_5v20, 2)   AS pts_zscore_5v20
                    FROM player_rolling_stats
                    WHERE game_recency_rank = 1
                      AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
                      AND position = '{rpos}'
                      AND pts_avg_20g BETWEEN {low} AND {high}
                      AND CAST(player_id AS VARCHAR) != '{rpid}'
                      AND gp_season >= 10
                    ORDER BY pts_zscore_5v20 DESC
                    LIMIT 8
                """)
            except Exception as e:
                st.error(f"Query error: {e}")
                df_rep = pd.DataFrame()

            if not df_rep.empty:
                rep_rows = ""
                for i, (_, rr) in enumerate(df_rep.iterrows(), 1):
                    z2 = float(rr["pts_zscore_5v20"])
                    z2c = "#f97316" if z2 >= 1.0 else ("#5a8f4e" if z2 >= 0.5 else ("#87ceeb" if z2 <= -0.8 else "#8896a8"))
                    bg = "rgba(255,255,255,0.02)" if i % 2 == 0 else "transparent"
                    rep_rows += (
                        f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);background:{bg};">'
                        f'<td style="padding:7px 14px;color:#fff;font-weight:600;font-size:13px;">{rr["name"]}</td>'
                        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;">{rr["team_abbr"]}</td>'
                        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{int(rr["gp_season"])}</td>'
                        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{rr["pts_avg_20g"]}</td>'
                        f'<td style="padding:7px 8px;color:#fff;font-size:12px;text-align:center;">{rr["pts_avg_5g"]}</td>'
                        f'<td style="padding:7px 8px;color:#8896a8;font-size:12px;text-align:center;">{rr["toi_min"]}</td>'
                        f'<td style="padding:7px 14px;color:{z2c};font-family:monospace;font-weight:700;text-align:center;">{z2:+.2f}σ</td>'
                        f'</tr>'
                    )
                st.html(
                    f'<div style="margin-top:12px;border:1px solid rgba(255,255,255,0.08);border-radius:5px;overflow:hidden;">'
                    f'<table style="width:100%;border-collapse:collapse;">'
                    f'<thead><tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);">'
                    f'<th style="padding:7px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:left;">PLAYER</th>'
                    f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;">TEAM</th>'
                    f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">GP</th>'
                    f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">PTS/20g</th>'
                    f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">PTS/5g</th>'
                    f'<th style="padding:7px 8px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">TOI</th>'
                    f'<th style="padding:7px 14px;color:#8896a8;font-size:10px;font-weight:600;text-align:center;">FORM</th>'
                    f'</tr></thead><tbody>{rep_rows}</tbody></table></div>'
                )

            if st.button("Close", key="btn_close_replace"):
                del st.session_state["find_replace_pid"]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – ROSTER BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_roster:
    rosters = userdb.roster_list()

    # Create new roster
    with st.expander("Create new roster", expanded=not rosters):
        new_name = st.text_input("Roster name", placeholder="e.g. My Dream Team", key="new_roster_name")
        if st.button("Create roster", key="btn_create_roster"):
            if new_name.strip():
                userdb.roster_create(new_name.strip())
                st.session_state.pop("new_roster_name", None)
                st.rerun()
            else:
                st.warning("Enter a name first.")

    if not rosters:
        st.info("No rosters yet — create one above.")
        st.stop()

    # Select active roster
    roster_map = {r["name"]: r["roster_id"] for r in rosters}
    sel_name = st.selectbox(
        "Active roster", list(roster_map.keys()),
        label_visibility="visible", key="active_roster",
    )
    rid = roster_map[sel_name]
    players = userdb.roster_players(rid)

    # ── Summary bar ───────────────────────────────────────────────────────────
    total_salary = sum(p["salary_k"] for p in players)
    pos_counts = {}
    for p in players:
        pos_counts[p["position"]] = pos_counts.get(p["position"], 0) + 1

    pos_html = " ".join(
        f"<span style='background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);"
        f"border-radius:3px;padding:2px 8px;font-size:11px;color:#fff;'>{pos} × {cnt}</span>"
        for pos, cnt in sorted(pos_counts.items())
    )
    st.markdown(
        f"""<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;
                        margin-bottom:16px;padding:10px 14px;
                        background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                        border-radius:5px;">
          <div>
            <span style="color:#8896a8;font-size:10px;text-transform:uppercase;">Players</span>
            <span style="color:#fff;font-weight:700;font-size:18px;margin-left:8px;">{len(players)}</span>
          </div>
          <div>
            <span style="color:#8896a8;font-size:10px;text-transform:uppercase;">Cap (est.)</span>
            <span style="color:#5a8f4e;font-weight:700;font-size:18px;margin-left:8px;">${total_salary:,}K</span>
          </div>
          <div style="display:flex;gap:6px;align-items:center;">{pos_html}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Roster table ──────────────────────────────────────────────────────────
    if not players:
        st.info("Roster is empty — add players from the Screener page or below.")
    else:
        # Fetch live stats for roster players
        pids_sql = "','".join(p["player_id"] for p in players)
        try:
            df_rost = query_fresh(f"""
                SELECT CAST(player_id AS VARCHAR) AS player_id,
                       ROUND(pts_avg_5g, 2)       AS pts_avg_5g,
                       ROUND(pts_avg_20g, 2)       AS pts_avg_20g,
                       ROUND(toi_avg_10g / 60, 1)  AS toi_min,
                       ROUND(pts_zscore_5v20, 2)   AS pts_zscore_5v20,
                       gp_season, goals_season, assists_season, pts_season
                FROM player_rolling_stats
                WHERE game_recency_rank = 1
                  AND CAST(player_id AS VARCHAR) IN ('{pids_sql}')
            """)
            live_map = {row["player_id"]: row for _, row in df_rost.iterrows()}
        except Exception:
            live_map = {}

        # Group by position
        pos_order = ["C", "L", "R", "D", "G"]
        groups = {}
        for p in players:
            groups.setdefault(p["position"] or "?", []).append(p)

        for pos in pos_order + [k for k in groups if k not in pos_order]:
            grp = groups.get(pos)
            if not grp:
                continue

            pos_label = {"C": "Centre", "L": "Left Wing", "R": "Right Wing", "D": "Defence", "G": "Goalie"}.get(pos, pos)
            st.markdown(
                f"<p style='color:#8896a8;font-size:10px;font-weight:600;text-transform:uppercase;"
                f"letter-spacing:0.08em;margin:14px 0 6px;'>{pos_label}</p>",
                unsafe_allow_html=True,
            )

            for p in grp:
                pid = p["player_id"]
                lv = live_map.get(pid, {})
                z = float(lv.get("pts_zscore_5v20", 0)) if lv else 0.0
                zc = "#f97316" if z >= 1.0 else ("#5a8f4e" if z >= 0.5 else ("#87ceeb" if z <= -0.8 else "#8896a8"))
                pts5 = lv.get("pts_avg_5g", "—") if lv else "—"
                toi = lv.get("toi_min", "—") if lv else "—"

                pc1, pc2, pc3, pc4, pc5 = st.columns([3, 1, 1, 2, 1])
                with pc1:
                    st.markdown(
                        f"<div style='padding:8px 0;'>"
                        f"<span style='color:#fff;font-weight:600;font-size:13px;'>{p['player_name']}</span>"
                        f"<span style='color:#8896a8;font-size:11px;margin-left:8px;'>{p['team_abbr']}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with pc2:
                    st.markdown(
                        f"<div style='padding:10px 0;color:{zc};font-family:monospace;font-weight:700;font-size:13px;'>{z:+.2f}σ</div>",
                        unsafe_allow_html=True,
                    )
                with pc3:
                    st.markdown(
                        f"<div style='padding:10px 0;color:#8896a8;font-size:12px;'>pts/5g: {pts5} · toi: {toi}</div>",
                        unsafe_allow_html=True,
                    )
                with pc4:
                    new_sal = st.number_input(
                        "Salary (K$)", min_value=0, max_value=15000,
                        value=p["salary_k"], step=100,
                        key=f"sal_{rid}_{pid}", label_visibility="collapsed",
                    )
                    if new_sal != p["salary_k"]:
                        userdb.roster_set_salary(rid, pid, new_sal)
                with pc5:
                    if st.button("Remove", key=f"rm_{rid}_{pid}"):
                        userdb.roster_remove_player(rid, pid)
                        st.rerun()

                st.markdown(
                    "<div style='border-bottom:1px solid rgba(255,255,255,0.04);'></div>",
                    unsafe_allow_html=True,
                )

    # Delete roster
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    with st.expander("Danger zone"):
        if st.button(f"Delete roster '{sel_name}'", key="btn_del_roster"):
            userdb.roster_delete(rid)
            st.rerun()

    # ── Add player manually ───────────────────────────────────────────────────
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:11px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Quick add to this roster</p>",
        unsafe_allow_html=True,
    )
    search_name = st.text_input("", placeholder="Search player name...", key="roster_search", label_visibility="collapsed")
    if search_name and len(search_name) >= 2:
        try:
            df_search = query_fresh(f"""
                SELECT CAST(player_id AS VARCHAR) AS player_id,
                       player_first_name || ' ' || player_last_name AS name,
                       team_abbr, position
                FROM player_rolling_stats
                WHERE game_recency_rank = 1
                  AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
                  AND (LOWER(player_first_name) LIKE LOWER('%{search_name}%')
                    OR LOWER(player_last_name)  LIKE LOWER('%{search_name}%'))
                LIMIT 10
            """)
        except Exception as e:
            st.error(f"{e}")
            df_search = pd.DataFrame()

        if not df_search.empty:
            options = {f"{r['name']} ({r['team_abbr']}, {r['position']})": r for _, r in df_search.iterrows()}
            chosen = st.selectbox("", list(options.keys()), label_visibility="collapsed", key="roster_pick")
            if st.button("Add to roster", key="btn_add_search"):
                r = options[chosen]
                userdb.roster_add_player(rid, str(r["player_id"]), r["name"], r["team_abbr"], r["position"])
                st.session_state.pop("roster_search", None)
                st.rerun()
