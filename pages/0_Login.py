"""Login / Sign up page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from lib.auth import sign_in, sign_up, get_user, _get_client

st.set_page_config(page_title="Login – THA Analytics", layout="wide")

# Already logged in → go to main app
if get_user():
    st.switch_page("app.py")

# ── Hide all Streamlit chrome ──────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"] { padding: 0 !important; }
[data-testid="block-container"] { padding: 0 !important; max-width: 100% !important; }
input, textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 5px !important;
    color: #f1f5f9 !important;
}
div[data-testid="stButton"] button {
    background: #5a8f4e !important;
    color: white !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 5px !important;
    height: 42px !important;
    font-size: 14px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Two-column layout ──────────────────────────────────────────────────────────
left, right = st.columns([1, 1], gap="small")

# ── LEFT: Value proposition ────────────────────────────────────────────────────
with left:
    st.markdown("""
    <div style="background:#050505; min-height:100vh; padding:60px 48px;
                display:flex; flex-direction:column; justify-content:center;">

      <div style="display:flex; align-items:center; gap:10px; margin-bottom:48px;">
        <div style="background:#5a8f4e; border-radius:6px; width:34px; height:34px;
                    display:flex; align-items:center; justify-content:center;
                    font-family:Arial,sans-serif; font-size:12px; font-weight:900; color:#fff;">
          THA
        </div>
        <div style="color:#fff; font-weight:800; font-size:16px; letter-spacing:-0.02em;">
          The Hockey Analytics
        </div>
      </div>

      <h1 style="color:#fff; font-size:36px; font-weight:900; letter-spacing:-0.03em;
                 line-height:1.15; margin-bottom:16px;">
        NHL analytics.<br>
        <span style="color:#5a8f4e;">Deeper than box scores.</span>
      </h1>

      <p style="color:#8896a8; font-size:15px; line-height:1.7; margin-bottom:40px; max-width:380px;">
        16 seasons of data, AI-generated insights and real-time form tracking —
        built for the hockey obsessed.
      </p>

      <div style="display:flex; flex-direction:column; gap:14px;">
        <div style="display:flex; align-items:flex-start; gap:12px;">
          <div style="background:rgba(90,143,78,0.15); border-radius:6px; padding:6px 8px;
                      color:#5a8f4e; font-size:14px; flex-shrink:0;">▲</div>
          <div>
            <div style="color:#fff; font-weight:600; font-size:13px;">Intelligence Feed</div>
            <div style="color:#8896a8; font-size:12px; margin-top:2px;">
              Daily AI insights on hot streaks, slumps and momentum shifts
            </div>
          </div>
        </div>
        <div style="display:flex; align-items:flex-start; gap:12px;">
          <div style="background:rgba(90,143,78,0.15); border-radius:6px; padding:6px 8px;
                      color:#5a8f4e; font-size:14px; flex-shrink:0;">≡</div>
          <div>
            <div style="color:#fff; font-weight:600; font-size:13px;">Player & Team History</div>
            <div style="color:#8896a8; font-size:12px; margin-top:2px;">
              Career arcs, trend charts and season-by-season breakdowns
            </div>
          </div>
        </div>
        <div style="display:flex; align-items:flex-start; gap:12px;">
          <div style="background:rgba(90,143,78,0.15); border-radius:6px; padding:6px 8px;
                      color:#5a8f4e; font-size:14px; flex-shrink:0;">⚡</div>
          <div>
            <div style="color:#fff; font-weight:600; font-size:13px;">AI Chat</div>
            <div style="color:#8896a8; font-size:12px; margin-top:2px;">
              Ask anything — the model queries 850K+ game records for you
            </div>
          </div>
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)

# ── RIGHT: Form ────────────────────────────────────────────────────────────────
with right:
    # Vertical spacer to roughly center the form with the left column
    st.markdown("<div style='height:120px;'></div>", unsafe_allow_html=True)

    # Mode toggle: login / signup / forgot
    mode = st.session_state.get("auth_mode", "login")

    if mode == "forgot":
        st.markdown(
            "<h2 style='color:#fff;font-size:22px;font-weight:800;"
            "letter-spacing:-0.02em;margin-bottom:6px;'>Reset password</h2>"
            "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>"
            "We'll send a reset link to your inbox.</p>",
            unsafe_allow_html=True,
        )
        reset_email = st.text_input("E-post", placeholder="din@email.com", key="reset_email")
        if st.button("Send reset link", use_container_width=True):
            if not reset_email:
                st.error("Fyll i din e-postadress.")
            else:
                try:
                    _get_client().auth.reset_password_email(
                        reset_email,
                        options={"redirect_to": "http://localhost:8501/Account"},
                    )
                    st.success("Länk skickad — kolla din e-post.")
                except Exception as e:
                    st.error(f"Fel: {e}")
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        if st.button("← Tillbaka till inloggning", key="back_login"):
            st.session_state["auth_mode"] = "login"
            st.rerun()

    elif mode == "signup":
        st.markdown(
            "<h2 style='color:#fff;font-size:22px;font-weight:800;"
            "letter-spacing:-0.02em;margin-bottom:6px;'>Skapa konto</h2>"
            "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>Gratis. Ingen kreditkort krävs.</p>",
            unsafe_allow_html=True,
        )
        new_email = st.text_input("E-post", placeholder="din@email.com", key="up_email")
        new_pass  = st.text_input("Lösenord", type="password",
                                   placeholder="Minst 6 tecken", key="up_pass")
        new_pass2 = st.text_input("Bekräfta lösenord", type="password",
                                   placeholder="Upprepa lösenordet", key="up_pass2")

        if st.button("Skapa konto", use_container_width=True, key="btn_signup"):
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
                    # Auto sign in after signup
                    ok2, err2 = sign_in(new_email, new_pass)
                    if ok2:
                        st.switch_page("app.py")
                    else:
                        st.success("Konto skapat! Logga in nedan.")
                        st.session_state["auth_mode"] = "login"
                        st.rerun()
                else:
                    st.error(err)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#8896a8;font-size:12px;'>Har du redan ett konto?</p>",
            unsafe_allow_html=True,
        )
        if st.button("Logga in istället", key="go_login"):
            st.session_state["auth_mode"] = "login"
            st.rerun()

    else:  # login
        st.markdown(
            "<h2 style='color:#fff;font-size:22px;font-weight:800;"
            "letter-spacing:-0.02em;margin-bottom:6px;'>Välkommen tillbaka</h2>"
            "<p style='color:#8896a8;font-size:13px;margin-bottom:24px;'>Logga in för att fortsätta.</p>",
            unsafe_allow_html=True,
        )
        email    = st.text_input("E-post", placeholder="din@email.com", key="in_email")
        password = st.text_input("Lösenord", type="password",
                                  placeholder="••••••••", key="in_pass")

        if st.button("Logga in", use_container_width=True, key="btn_login"):
            if not email or not password:
                st.error("Fyll i e-post och lösenord.")
            else:
                with st.spinner(""):
                    ok, err = sign_in(email, password)
                if ok:
                    st.switch_page("app.py")
                else:
                    st.error(err)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Skapa konto", key="go_signup"):
                st.session_state["auth_mode"] = "signup"
                st.rerun()
        with c2:
            if st.button("Glömt lösenord?", key="go_forgot"):
                st.session_state["auth_mode"] = "forgot"
                st.rerun()

