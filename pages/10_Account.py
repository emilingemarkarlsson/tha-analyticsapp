"""Account page – profile and settings."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from lib.auth import require_login, sign_out, _get_client
from lib.sidebar import render as _render_sidebar
from lib.components import page_header, data_source_footer

st.set_page_config(page_title="Account – THA Analytics", layout="wide")
_render_sidebar()
user = require_login()

page_header("My Account", "Profile and settings")

# ── Profile card ───────────────────────────────────────────────────────────────
st.html(f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
            border-radius:8px;padding:20px 24px;max-width:480px;margin-bottom:24px;">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;">
    <div style="background:#5a8f4e;border-radius:50%;width:44px;height:44px;
                display:flex;align-items:center;justify-content:center;
                font-weight:800;font-size:18px;color:#fff;flex-shrink:0;">
      {user['email'][0].upper()}
    </div>
    <div>
      <div style="color:#fff;font-weight:700;font-size:15px;">{user['email']}</div>
      <div style="color:#5a8f4e;font-size:11px;font-weight:600;
                  text-transform:uppercase;letter-spacing:0.06em;margin-top:2px;">
        Free plan
      </div>
    </div>
  </div>
  <div style="border-top:1px solid rgba(255,255,255,0.06);padding-top:12px;
              color:#8896a8;font-size:11px;line-height:1.8;">
    <div>Member since: <span style="color:#fff;">{user['created_at'][:10]}</span></div>
  </div>
</div>
""")

# ── Change password ────────────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
    "letter-spacing:0.08em;color:#8896a8;margin-bottom:8px;'>Change password</p>",
    unsafe_allow_html=True,
)

col, _ = st.columns([1, 2])
with col:
    new_pw = st.text_input("New password", type="password", key="new_pw",
                            placeholder="At least 6 characters")
    new_pw2 = st.text_input("Confirm password", type="password", key="new_pw2",
                             placeholder="Repeat password")
    if st.button("Update password", key="btn_update_pw"):
        if not new_pw:
            st.error("Please enter a new password.")
        elif new_pw != new_pw2:
            st.error("Passwords don't match.")
        elif len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            try:
                sb = _get_client()
                sb.auth.update_user({"password": new_pw})
                st.success("Password updated.")
            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

# ── Sign out ───────────────────────────────────────────────────────────────────
if st.button("Sign out", key="btn_logout"):
    sign_out()
    st.switch_page("pages/0_Login.py")

data_source_footer()
