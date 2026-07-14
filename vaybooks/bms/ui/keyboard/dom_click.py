"""Click existing Streamlit widgets via JS (no new UI surfaces)."""

from __future__ import annotations

import streamlit.components.v1 as components


def click_popover_by_key(widget_key: str) -> None:
    """Programmatically click the popover trigger keyed ``widget_key``.

    Uses ``window.parent.document`` (Streamlit app frame) with retries so the
    click runs after the keyed popover button is in the DOM — more reliable in
    Firefox than a one-shot ``streamlit_js_eval`` expression.
    """
    safe = (
        widget_key.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', "&quot;")
    )
    html = f"""
<!DOCTYPE html><html><body>
<script>
(function () {{
  const key = "{safe}";
  function tryClick() {{
    try {{
      const doc = window.parent && window.parent.document
        ? window.parent.document
        : document;
      const roots = Array.from(doc.querySelectorAll('[class*="st-key-' + key + '"]'));
      for (const root of roots) {{
        const btn = root.querySelector('button');
        if (btn) {{
          btn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window.parent }}));
          btn.click();
          return true;
        }}
      }}
    }} catch (e) {{}}
    return false;
  }}
  tryClick();
  setTimeout(tryClick, 50);
  setTimeout(tryClick, 150);
  setTimeout(tryClick, 350);
}})();
</script>
</body></html>
"""
    try:
        components.html(html, height=0, width=0)
    except Exception:
        try:
            from streamlit_js_eval import streamlit_js_eval

            streamlit_js_eval(
                js_expressions=f"""
                (() => {{
                  const doc = window.parent?.document || document;
                  const roots = Array.from(doc.querySelectorAll('[class*="st-key-{safe}"]'));
                  for (const root of roots) {{
                    const btn = root.querySelector('button');
                    if (btn) {{ btn.click(); return true; }}
                  }}
                  return false;
                }})()
                """,
                key=f"kb_click_{widget_key}",
            )
        except Exception:
            pass
