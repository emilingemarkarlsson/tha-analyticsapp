"""Account page – profile, plan and settings."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from lib.auth import require_login, sign_out, _get_client
from lib.sidebar import render as _render_sidebar
from lib.components import page_header, data_source_footer
from lib.entitlements import (
    get_plan, plan_badge_html, PLAN_LABELS, PLAN_PRICES, PLAN_COLORS,
    AI_QUERY_LIMITS, WATCHLIST_LIMITS, ai_queries_remaining,
)
from lib import userdb

st.set_page_config(page_title="Account – THA Analytics", layout="wide", initial_sidebar_state="expanded")
_render_sidebar()
user = require_login()
uid  = (user or {}).get("id", "")

page_header("My Account", "Plan, profil och inställningar")

# Ensure user row exists in local DB
if uid:
    userdb.upsert_user(uid)

plan       = get_plan(uid)
plan_color = PLAN_COLORS.get(plan, "#8896a8")
plan_label = PLAN_LABELS.get(plan, plan.title())
plan_price = PLAN_PRICES.get(plan, "")

# ── Profile + plan card ────────────────────────────────────────────────────────
col_profile, col_plans = st.columns([1, 2], gap="large")

with col_profile:
    st.html(f"""
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                border-radius:8px;padding:20px 24px;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;">
        <div style="background:{plan_color};border-radius:50%;width:44px;height:44px;
                    display:flex;align-items:center;justify-content:center;
                    font-weight:800;font-size:18px;color:#fff;flex-shrink:0;">
          {user['email'][0].upper()}
        </div>
        <div>
          <div style="color:#fff;font-weight:700;font-size:15px;">{user['email']}</div>
          <div style="margin-top:4px;">{plan_badge_html(plan)}</div>
        </div>
      </div>
      <div style="border-top:1px solid rgba(255,255,255,0.06);padding-top:12px;
                  color:#8896a8;font-size:11px;line-height:1.8;">
        <div>Medlem sedan: <span style="color:#fff;">{user['created_at'][:10]}</span></div>
        <div>Plan: <span style="color:{plan_color};font-weight:600;">{plan_label}
            {f'· {plan_price}' if plan != 'free' else ''}</span></div>
      </div>
    </div>
    """)

    # Usage summary
    ai_left = ai_queries_remaining(uid)
    wl_limit = WATCHLIST_LIMITS.get(plan, 0)
    wl_used  = userdb.watchlist_count(uid)
    ai_limit = AI_QUERY_LIMITS.get(plan, 5)

    st.html(f"""
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);
                border-radius:8px;padding:16px 20px;margin-bottom:16px;">
      <p style="color:#8896a8;font-size:9px;font-weight:700;text-transform:uppercase;
                letter-spacing:0.1em;margin-bottom:10px;">Användning idag</p>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div>
          <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
            <span style="color:#8896a8;font-size:11px;">AI-frågor</span>
            <span style="color:#fff;font-size:11px;font-family:monospace;">
              {ai_limit - ai_left if ai_limit < 9999 else '∞'} /
              {'∞' if ai_limit >= 9999 else ai_limit}
            </span>
          </div>
          {'<div style="background:rgba(255,255,255,0.06);border-radius:2px;height:4px;"><div style="background:#5a8f4e;border-radius:2px;height:4px;width:' + str(min(100, round((ai_limit - ai_left) / ai_limit * 100))) + '%"></div></div>' if ai_limit < 9999 else ''}
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
            <span style="color:#8896a8;font-size:11px;">Watchlist</span>
            <span style="color:#fff;font-size:11px;font-family:monospace;">
              {wl_used} / {'∞' if wl_limit >= 9999 else wl_limit}
            </span>
          </div>
          {'<div style="background:rgba(255,255,255,0.06);border-radius:2px;height:4px;"><div style="background:#87ceeb;border-radius:2px;height:4px;width:' + str(min(100, round(wl_used / wl_limit * 100)) if wl_limit > 0 else 0) + '%"></div></div>' if wl_limit < 9999 and wl_limit > 0 else ''}
        </div>
      </div>
    </div>
    """)

with col_plans:
    # ── Upgrade panel ──────────────────────────────────────────────────────────
    st.markdown(
        "<p style='color:rgba(255,255,255,0.35);font-size:9px;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;'>Välj plan</p>",
        unsafe_allow_html=True,
    )

    plan_features = {
        "free": [
            "NHL Intelligence Feed (3 insikter)",
            "Standings & Players (top 50)",
            "Deep Dive – Overview-tab",
            "5 AI-frågor per dag",
            "Playoff-bracket (aktuell)",
        ],
        "base": [
            "Allt i Free",
            "Deep Dive – Career & Splits-tabs",
            "Watchlist (10 spelare)",
            "30 AI-frågor per dag",
            "5 säsongers historik",
            "Player Finder – alla filter",
            "Intelligence Feed – alla insikter",
        ],
        "plus": [
            "Allt i Base",
            "Watchlist – obegränsat",
            "Obegränsat AI-chat",
            "Alla 16 säsongers historik",
            "SHL-data (kommer snart)",
            "Export till CSV",
        ],
    }

    plan_cols = st.columns(3, gap="medium")
    for i, (p, feats) in enumerate(plan_features.items()):
        color  = PLAN_COLORS[p]
        label  = PLAN_LABELS[p]
        price  = PLAN_PRICES[p]
        active = (plan == p)
        border = f"2px solid {color}" if active else "1px solid rgba(255,255,255,0.08)"
        feat_html = "".join(
            f'<li style="color:#8896a8;font-size:11px;padding:2px 0;">{f}</li>'
            for f in feats
        )
        with plan_cols[i]:
            st.html(f"""
            <div style="background:rgba(255,255,255,0.02);border:{border};
                        border-radius:8px;padding:16px 18px;height:100%;">
              <div style="display:flex;align-items:center;justify-content:space-between;
                          margin-bottom:12px;">
                <span style="color:{color};font-weight:800;font-size:14px;">{label}</span>
                {'<span style="background:' + color + '22;color:' + color + ';font-size:9px;font-weight:700;padding:2px 8px;border-radius:3px;">AKTIV</span>' if active else ''}
              </div>
              <div style="color:#fff;font-weight:700;font-size:20px;margin-bottom:12px;">
                {price}
              </div>
              <ul style="list-style:none;padding:0;margin:0 0 12px;">
                {feat_html}
              </ul>
            </div>
            """)
            if not active and p != "free":
                if st.button(f"Uppgradera till {label}", key=f"btn_upgrade_{p}",
                             use_container_width=True, type="primary"):
                    st.info("Betalning via Stripe kommer snart. Kontakta oss på hockeyanalytics@tha.se")

st.markdown("<hr style='border-color:rgba(255,255,255,0.08);margin:24px 0;'>", unsafe_allow_html=True)

# ── Change password ────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Byt lösenord</p>",
    unsafe_allow_html=True,
)

col, _ = st.columns([1, 2])
with col:
    new_pw  = st.text_input("Nytt lösenord", type="password", key="new_pw",
                             placeholder="Minst 6 tecken")
    new_pw2 = st.text_input("Bekräfta lösenord", type="password", key="new_pw2",
                              placeholder="Upprepa lösenordet")
    if st.button("Uppdatera lösenord", key="btn_update_pw"):
        if not new_pw:
            st.error("Ange ett nytt lösenord.")
        elif new_pw != new_pw2:
            st.error("Lösenorden matchar inte.")
        elif len(new_pw) < 6:
            st.error("Lösenordet måste vara minst 6 tecken.")
        else:
            try:
                _get_client().auth.update_user({"password": new_pw})
                st.success("Lösenord uppdaterat.")
            except Exception as e:
                st.error(f"Fel: {e}")

st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

# ── Sign out ───────────────────────────────────────────────────────────────────
if st.button("Logga ut", key="btn_logout"):
    sign_out()
    st.switch_page("pages/0_Login.py")

data_source_footer()
