"""Umami analytics – injects tracking script via st.components.v1.html(height=0).

Called once from sidebar.render() so every page is covered automatically.
Auto-detects page name from the running script path.
"""
import os
import streamlit.components.v1 as components

_SCRIPT_URL = "https://umami.theunnamedroads.com/script.js"
_WEBSITE_ID = "ec05cc8e-e3f0-4955-88df-14a8a68318f4"

# Map script filenames → clean page names
_PAGE_NAMES: dict[str, str] = {
    "app":              "Intelligence Feed",
    "0_Login":          "Login",
    "1_Deep_Dive":      "Deep Dive",
    "2_Standings":      "Standings",
    "3_Players":        "Players",
    "4_Teams":          "Teams",
    "5_Chat":           "Ask AI",
    "6_Screener":       "Player Finder",
    "7_Watchlist":      "Watchlist",
    "8_Player_History": "Player History",
    "9_Team_History":   "Team History",
    "10_Account":       "Account",
    "11_Goalies":       "Goalies",
    "12_Playoffs":      "Playoffs",
    "13_Compare":       "Compare",
}


def _current_page() -> tuple[str, str]:
    """Return (slug, title) for the currently running Streamlit script."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx and ctx.script_path:
            stem = os.path.basename(ctx.script_path).replace(".py", "")
            title = _PAGE_NAMES.get(stem, stem.replace("_", " "))
            slug  = "/" + title.lower().replace(" ", "-")
            return slug, title
    except Exception:
        pass
    return "/unknown", "Unknown"


def inject() -> None:
    """Inject Umami pageview tracker. Call from sidebar.render()."""
    slug, title = _current_page()
    # data-auto-track="false" — we fire one manual track() call with the
    # correct page slug instead of letting Umami use the iframe URL.
    components.html(
        f"""
<script>
(function() {{
  var s = document.createElement('script');
  s.src   = '{_SCRIPT_URL}';
  s.defer = true;
  s.setAttribute('data-website-id', '{_WEBSITE_ID}');
  s.setAttribute('data-auto-track', 'false');
  s.setAttribute('data-host-url',   'https://umami.theunnamedroads.com');
  s.onload = function() {{
    if (window.umami) {{
      window.umami.track(function(props) {{
        return Object.assign({{}}, props, {{
          url:      '{slug}',
          title:    '{title}',
          hostname: 'tha-analyticsapp.streamlit.app'
        }});
      }});
    }}
  }};
  document.head.appendChild(s);
}})();
</script>
""",
        height=0,
    )
