"""Login / Sign up page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from lib.auth import sign_in, sign_up, get_user

st.set_page_config(page_title="Login – THA Analytics", layout="centered")

# Already logged in → go to main app
if get_user():
    st.switch_page("app.py")

# ── Page CSS ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Logo ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 48px 0 32px;">
  <div style="display:inline-flex; align-items:center; gap:10px;">
    <div style="background:#5a8f4e; border-radius:6px; width:36px; height:36px;
                display:flex; align-items:center; justify-content:center;
                font-family:Arial,sans-serif; font-size:13px; font-weight:900; color:#fff;">
      THA
    </div>
    <div style="text-align:left;">
      <div style="color:#fff; font-weight:800; font-size:18px; letter-spacing:-0.03em; line-height:1.1;">
        The Hockey Analytics
      </div>
      <div style="color:#5a8f4e; font-size:10px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase;">
        NHL · Analytics
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs: Sign in / Sign up ────────────────────────────────────────────────────
tab_in, tab_up = st.tabs(["Logga in", "Skapa konto"])

with tab_in:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    email = st.text_input("E-post", key="in_email", placeholder="din@email.com")
    password = st.text_input("Lösenord", key="in_pass", type="password", placeholder="••••••••")

    if st.button("Logga in", use_container_width=True, type="primary", key="btn_login"):
        if not email or not password:
            st.error("Fyll i e-post och lösenord.")
        else:
            with st.spinner(""):
                ok, err = sign_in(email, password)
            if ok:
                st.switch_page("app.py")
            else:
                st.error(err)

with tab_up:
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#8896a8;font-size:12px;margin-bottom:12px;'>"
        "Skapa ett gratis konto för att komma igång.</p>",
        unsafe_allow_html=True,
    )
    new_email = st.text_input("E-post", key="up_email", placeholder="din@email.com")
    new_pass = st.text_input("Lösenord", key="up_pass", type="password",
                              placeholder="Minst 6 tecken")
    new_pass2 = st.text_input("Bekräfta lösenord", key="up_pass2", type="password",
                               placeholder="Upprepa lösenordet")

    if st.button("Skapa konto", use_container_width=True, type="primary", key="btn_signup"):
        if not new_email or not new_pass:
            st.error("Fyll i e-post och lösenord.")
        elif new_pass != new_pass2:
            st.error("Lösenorden matchar inte.")
        elif len(new_pass) < 6:
            st.error("Lösenordet måste vara minst 6 tecken.")
        else:
            with st.spinner(""):
                ok, err = sign_up(new_email, new_pass)
            if ok:
                st.success("Konto skapat! Kolla din e-post för att bekräfta, logga sedan in.")
            else:
                st.error(err)
