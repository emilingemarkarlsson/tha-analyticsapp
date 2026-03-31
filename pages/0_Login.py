"""Login / Sign up page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from lib.auth import sign_in, sign_up, get_user, _get_client

st.set_page_config(page_title="Login – THA Analytics", layout="wide")

if get_user():
    st.switch_page("app.py")

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stAppViewContainer"] { background: #050505; }
[data-testid="block-container"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
}
[data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stColumn"] > div { padding: 0 !important; }
input, textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 6px !important;
    color: #f1f5f9 !important;
    font-size: 14px !important;
}
/* Primary submit button */
button[kind="primaryFormSubmit"],
button[data-testid="baseButton-primaryFormSubmit"],
div[data-testid="stFormSubmitButton"] > button {
    background: #5a8f4e !important;
    color: white !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    height: 44px !important;
    font-size: 15px !important;
    width: 100% !important;
}
/* Secondary buttons — text link style */
button[kind="secondary"],
button[data-testid="baseButton-secondary"],
div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #8896a8 !important;
    border: none !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 4px 0 !important;
    height: auto !important;
    min-height: unset !important;
    box-shadow: none !important;
    text-decoration: underline !important;
    text-underline-offset: 3px !important;
}
div[data-testid="stButton"] > button:hover {
    color: #fff !important;
    background: transparent !important;
}
/* Labels — normal case */
label p, .stTextInput label p, .stPassword label p {
    color: #8896a8 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
}
</style>
""", unsafe_allow_html=True)

left, right = st.columns([1, 1], gap="small")

# ── LEFT: value proposition ────────────────────────────────────────────────────
with left:
    st.markdown("""
<div style="padding: 64px 56px 40px; height: 100vh; box-sizing: border-box;
            border-right: 1px solid rgba(255,255,255,0.06);">

  <div style="display:flex; align-items:center; gap:10px; margin-bottom:56px;">
    <div style="background:#5a8f4e; border-radius:6px; width:32px; height:32px;
                display:flex; align-items:center; justify-content:center;
                font-family:Arial,sans-serif; font-size:11px; font-weight:900; color:#fff;">
      THA
    </div>
    <span style="color:#fff; font-weight:800; font-size:15px; letter-spacing:-0.02em;">
      The Hockey Analytics
    </span>
  </div>

  <h1 style="color:#fff; font-size:38px; font-weight:900; letter-spacing:-0.03em;
             line-height:1.15; margin:0 0 16px;">
    NHL analytics.<br>
    <span style="color:#5a8f4e;">Deeper than box scores.</span>
  </h1>

  <p style="color:#8896a8; font-size:15px; line-height:1.7; margin:0 0 48px; max-width:360px;">
    16 seasons of data, AI-generated insights and real-time form tracking —
    built for the hockey obsessed.
  </p>

  <div style="display:flex; flex-direction:column; gap:20px;">
    <div style="display:flex; align-items:flex-start; gap:14px;">
      <div style="background:rgba(90,143,78,0.15); border:1px solid rgba(90,143,78,0.25);
                  border-radius:6px; padding:5px 9px; color:#5a8f4e; font-size:13px;
                  flex-shrink:0; margin-top:1px;">▲</div>
      <div>
        <div style="color:#fff; font-weight:600; font-size:13px; margin-bottom:3px;">Intelligence Feed</div>
        <div style="color:#8896a8; font-size:12px; line-height:1.5;">
          Daily AI insights on hot streaks, slumps and momentum shifts
        </div>
      </div>
    </div>
    <div style="display:flex; align-items:flex-start; gap:14px;">
      <div style="background:rgba(90,143,78,0.15); border:1px solid rgba(90,143,78,0.25);
                  border-radius:6px; padding:5px 9px; color:#5a8f4e; font-size:13px;
                  flex-shrink:0; margin-top:1px;">≡</div>
      <div>
        <div style="color:#fff; font-weight:600; font-size:13px; margin-bottom:3px;">Player & Team History</div>
        <div style="color:#8896a8; font-size:12px; line-height:1.5;">
          Career arcs, trend charts and season-by-season breakdowns
        </div>
      </div>
    </div>
    <div style="display:flex; align-items:flex-start; gap:14px;">
      <div style="background:rgba(90,143,78,0.15); border:1px solid rgba(90,143,78,0.25);
                  border-radius:6px; padding:5px 9px; color:#5a8f4e; font-size:13px;
                  flex-shrink:0; margin-top:1px;">⚡</div>
      <div>
        <div style="color:#fff; font-weight:600; font-size:13px; margin-bottom:3px;">AI Chat</div>
        <div style="color:#8896a8; font-size:12px; line-height:1.5;">
          Ask anything — the model queries 850 K+ game records for you
        </div>
      </div>
    </div>
  </div>

</div>
""", unsafe_allow_html=True)

# ── RIGHT: auth form ───────────────────────────────────────────────────────────
with right:
    mode = st.session_state.get("auth_mode", "login")

    # ── Forgot password ────────────────────────────────────────────────────────
    if mode == "forgot":
        st.markdown(
            "<h2 style='color:#fff;font-size:24px;font-weight:800;"
            "letter-spacing:-0.02em;margin:64px 0 6px;'>Reset password</h2>"
            "<p style='color:#8896a8;font-size:13px;margin:0 0 28px;'>"
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
        st.markdown(
            "<div style='margin-top:12px;'>"
            "<a href='/Login' target='_self' style='color:#8896a8;font-size:13px;"
            "text-decoration:underline;text-underline-offset:3px;'>← Tillbaka</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Sign up ────────────────────────────────────────────────────────────────
    elif mode == "signup":
        st.markdown(
            "<h2 style='color:#fff;font-size:24px;font-weight:800;"
            "letter-spacing:-0.02em;margin:64px 0 6px;'>Skapa konto</h2>"
            "<p style='color:#8896a8;font-size:13px;margin:0 0 28px;'>"
            "Gratis. Inget kreditkort krävs.</p>",
            unsafe_allow_html=True,
        )
        with st.form("signup_form"):
            new_email = st.text_input("E-post", placeholder="din@email.com")
            new_pass  = st.text_input("Lösenord", type="password", placeholder="Minst 6 tecken")
            new_pass2 = st.text_input("Bekräfta lösenord", type="password", placeholder="Upprepa lösenordet")
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Skapa konto", use_container_width=True)

        if submitted:
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
                    ok2, _ = sign_in(new_email, new_pass)
                    if ok2:
                        st.switch_page("app.py")
                    else:
                        st.success("Konto skapat! Logga in nedan.")
                        st.session_state["auth_mode"] = "login"
                        st.rerun()
                else:
                    st.error(err)
        st.markdown(
            "<div style='margin-top:16px;'>"
            "<a href='/Login' target='_self' style='color:#8896a8;font-size:13px;"
            "text-decoration:underline;text-underline-offset:3px;'>← Logga in istället</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Login ──────────────────────────────────────────────────────────────────
    else:
        st.markdown(
            "<h2 style='color:#fff;font-size:24px;font-weight:800;"
            "letter-spacing:-0.02em;margin:64px 0 6px;'>Välkommen tillbaka</h2>"
            "<p style='color:#8896a8;font-size:13px;margin:0 0 24px;'>"
            "Logga in för att fortsätta.</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email    = st.text_input("E-post", placeholder="din@email.com")
            password = st.text_input("Lösenord", type="password", placeholder="••••••••")
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Logga in", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Fyll i e-post och lösenord.")
            else:
                with st.spinner(""):
                    ok, err = sign_in(email, password)
                if ok:
                    st.switch_page("app.py")
                else:
                    st.error(err)

        st.markdown(
            "<div style='margin-top:16px; display:flex; gap:24px;'>"
            "<a href='/Login?mode=signup' target='_self' style='color:#8896a8;font-size:13px;"
            "text-decoration:underline;text-underline-offset:3px;'>Skapa konto →</a>"
            "<a href='/Login?mode=forgot' target='_self' style='color:#8896a8;font-size:13px;"
            "text-decoration:underline;text-underline-offset:3px;'>Glömt lösenord?</a>"
            "</div>",
            unsafe_allow_html=True,
        )
        # Handle query param mode switching
        qp = st.query_params
        if qp.get("mode") == "signup":
            st.session_state["auth_mode"] = "signup"
            st.query_params.clear()
            st.rerun()
        elif qp.get("mode") == "forgot":
            st.session_state["auth_mode"] = "forgot"
            st.query_params.clear()
            st.rerun()

