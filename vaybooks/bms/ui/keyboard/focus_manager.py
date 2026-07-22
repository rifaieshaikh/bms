"""Programmatic focus + Enter trail, including bridge into ``st.data_editor``.

Header widgets use ``st-key-*``. After the last chain key (e.g. Expected date),
focus is moved into the keyed data_editor via canvas/overlay click. Inside the
editor, Enter commits then Tabs to the next cell (Item → Qty → Rate).
"""

from __future__ import annotations

import json
from typing import Sequence

import streamlit.components.v1 as components


def inject_focus_manager(
    chain: Sequence[str],
    *,
    initial_key: str | None = None,
    restore_key: str | None = None,
    add_line_key: str | None = None,
    data_editor_key: str | None = None,
    component_key: str = "focus_mgr",
) -> None:
    """Focus ``initial_key``/``restore_key`` and advance along ``chain`` on Enter.

    When ``data_editor_key`` is set and Enter is pressed on the last chain widget,
    focus moves into that ``st.data_editor`` (first Item cell). While focus is
    inside the editor, Enter is translated to Tab so Qty/Rate remain reachable
    without replacing the table.
    """
    safe_chain = [str(k) for k in chain if k]
    if not safe_chain and not data_editor_key:
        return
    focus_to = restore_key or initial_key or (safe_chain[0] if safe_chain else "")
    payload = {
        "chain": safe_chain,
        "focusTo": focus_to,
        "addLineKey": add_line_key or "",
        "dataEditorKey": data_editor_key or "",
        "nonce": str(component_key),
    }
    data = json.dumps(payload).replace("</", "<\\/")
    html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;">
<script>
(function () {{
  const cfg = {data};
  const win = window.parent || window;
  const doc = win.document || document;

  win.__vayFocusMgrCfg = cfg;

  function scopeRoot() {{
    try {{
      const dialog = doc.querySelector('[role="dialog"]');
      if (dialog) return dialog;
    }} catch (e) {{}}
    return doc;
  }}

  function rootsFor(key) {{
    if (!key) return [];
    try {{
      const root = scopeRoot();
      const nodes = Array.from(root.querySelectorAll('[class*="st-key-' + key + '"]'));
      if (nodes.length) return nodes;
      return Array.from(doc.querySelectorAll('[class*="st-key-' + key + '"]'));
    }} catch (e) {{
      return [];
    }}
  }}

  function focusable(root) {{
    if (!root) return null;
    const selectors = [
      'input:not([type="hidden"]):not([disabled])',
      'textarea:not([disabled])',
      'select:not([disabled])',
      '[role="combobox"]',
      '[contenteditable="true"]',
    ];
    for (const sel of selectors) {{
      const el = root.querySelector(sel);
      if (el) return el;
    }}
    return null;
  }}

  function focusKey(key) {{
    const roots = rootsFor(key);
    for (const root of roots) {{
      const el = focusable(root);
      if (!el) continue;
      try {{
        el.focus({{ preventScroll: false }});
        if (typeof el.select === 'function' && el.tagName === 'INPUT') {{
          try {{ el.select(); }} catch (e) {{}}
        }}
        return true;
      }} catch (e) {{}}
    }}
    return false;
  }}

  function clickKey(key) {{
    if (!key) return false;
    const roots = rootsFor(key);
    for (const root of roots) {{
      const btn = root.querySelector('button');
      if (btn) {{
        try {{
          btn.dispatchEvent(new MouseEvent('click', {{
            bubbles: true, cancelable: true, view: win
          }}));
          btn.click();
          return true;
        }} catch (e) {{}}
      }}
    }}
    return false;
  }}

  function classKey(node) {{
    const cls = (node && node.className && String(node.className)) || '';
    const matches = cls.match(/st-key-[\\w-]+/g) || [];
    if (!matches.length) return null;
    let best = matches[0];
    for (const m of matches) {{
      if (m.length > best.length) best = m;
    }}
    return best.slice('st-key-'.length);
  }}

  function activeKey() {{
    const active = doc.activeElement;
    if (!active) return null;
    let node = active;
    while (node && node !== doc.body) {{
      const key = classKey(node);
      if (key) return key;
      node = node.parentElement;
    }}
    return null;
  }}

  function listOpen(el) {{
    if (!el) return false;
    let node = el;
    while (node && node !== doc.body) {{
      if (node.getAttribute && node.getAttribute('aria-expanded') === 'true') return true;
      node = node.parentElement;
    }}
    try {{
      const pop = doc.querySelector('[data-baseweb="popover"] [role="listbox"]');
      if (pop) return true;
      const lb = doc.querySelector('[role="listbox"]');
      if (lb && lb.offsetParent !== null) return true;
    }} catch (e) {{}}
    return false;
  }}

  function fireAt(el, x, y) {{
    const opts = {{
      bubbles: true, cancelable: true, view: win,
      clientX: x, clientY: y, button: 0, buttons: 1
    }};
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function (type) {{
      try {{ el.dispatchEvent(new MouseEvent(type, opts)); }} catch (e) {{}}
    }});
  }}

  function focusDataEditor(editorKey) {{
    if (!editorKey) return false;
    const roots = rootsFor(editorKey);
    for (const root of roots) {{
      try {{
        // Already editing — focus overlay input
        const existing = root.querySelector(
          'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), [contenteditable="true"]'
        );
        if (existing) {{
          existing.focus({{ preventScroll: false }});
          if (typeof existing.select === 'function') {{
            try {{ existing.select(); }} catch (e) {{}}
          }}
          return true;
        }}

        const canvas = root.querySelector('canvas');
        if (canvas) {{
          const rect = canvas.getBoundingClientRect();
          // First data cell roughly under header, left side (Item column)
          const x = rect.left + Math.min(48, Math.max(24, rect.width * 0.08));
          const y = rect.top + Math.min(52, Math.max(36, rect.height * 0.12));
          const hit = doc.elementFromPoint(x, y) || canvas;
          fireAt(hit, x, y);
          // Double-click to enter edit mode on Item
          setTimeout(function () {{
            fireAt(hit, x, y);
            fireAt(hit, x, y);
            setTimeout(function () {{
              const inp = root.querySelector(
                'input:not([type="hidden"]):not([disabled]), textarea:not([disabled])'
              );
              if (inp) {{
                inp.focus({{ preventScroll: false }});
                if (typeof inp.select === 'function') {{
                  try {{ inp.select(); }} catch (e) {{}}
                }}
              }} else {{
                try {{ canvas.focus(); }} catch (e) {{}}
              }}
            }}, 40);
          }}, 30);
          return true;
        }}

        const frame = root.querySelector('[data-testid="stDataFrame"], [data-testid="stDataEditor"]') || root;
        try {{ frame.focus(); }} catch (e) {{}}
        const any = focusable(root);
        if (any) {{ any.focus(); return true; }}
      }} catch (e) {{}}
    }}
    return false;
  }}

  function nodeInsideDataEditor(node) {{
    const c = win.__vayFocusMgrCfg || cfg;
    if (!c.dataEditorKey || !node) return false;
    let cur = node;
    while (cur && cur !== doc.body) {{
      const key = classKey(cur);
      if (key === c.dataEditorKey) return true;
      if (key && key.indexOf(c.dataEditorKey) === 0) return true;
      cur = cur.parentElement;
    }}
    return false;
  }}

  function sendTab(target) {{
    const el = target || doc.activeElement || doc.body;
    const opts = {{
      key: 'Tab', code: 'Tab', keyCode: 9, which: 9,
      bubbles: true, cancelable: true, view: win
    }};
    try {{
      el.dispatchEvent(new KeyboardEvent('keydown', opts));
      el.dispatchEvent(new KeyboardEvent('keyup', opts));
    }} catch (e) {{}}
  }}

  function advanceFrom(key) {{
    const c = win.__vayFocusMgrCfg || cfg;
    const idx = c.chain.indexOf(key);
    if (idx < 0) return;
    if (idx >= c.chain.length - 1) {{
      if (c.dataEditorKey) {{
        focusDataEditor(c.dataEditorKey);
        return;
      }}
      if (c.addLineKey) clickKey(c.addLineKey);
      return;
    }}
    focusKey(c.chain[idx + 1]);
  }}

  function onKeyDown(ev) {{
    if (ev.key !== 'Enter' || ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey) {{
      return;
    }}
    const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toLowerCase() : '';
    if (tag === 'textarea') return;
    if (listOpen(ev.target)) return;

    const c = win.__vayFocusMgrCfg || cfg;

    // Inside data_editor: Enter → let commit happen, then Tab to next cell
    if (nodeInsideDataEditor(ev.target) || nodeInsideDataEditor(doc.activeElement)) {{
      // Don't steal Enter from open dropdowns (already handled by listOpen)
      setTimeout(function () {{
        if (listOpen(doc.activeElement)) return;
        sendTab(doc.activeElement);
      }}, 10);
      return;
    }}

    const key = activeKey();
    if (!key || c.chain.indexOf(key) < 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    setTimeout(function () {{ advanceFrom(key); }}, 0);
  }}

  if (!win.__vayFocusMgrListener) {{
    win.__vayFocusMgrListener = onKeyDown;
    doc.addEventListener('keydown', onKeyDown, true);
  }} else {{
    try {{
      doc.removeEventListener('keydown', win.__vayFocusMgrListener, true);
    }} catch (e) {{}}
    win.__vayFocusMgrListener = onKeyDown;
    doc.addEventListener('keydown', onKeyDown, true);
  }}

  function tryFocus() {{
    const c = win.__vayFocusMgrCfg || cfg;
    if (!c.focusTo) return;
    if (c.dataEditorKey && c.focusTo === c.dataEditorKey) {{
      focusDataEditor(c.dataEditorKey);
      return;
    }}
    focusKey(c.focusTo);
  }}
  tryFocus();
  setTimeout(tryFocus, 40);
  setTimeout(tryFocus, 120);
  setTimeout(tryFocus, 280);
  setTimeout(tryFocus, 500);
}})();
</script>
</body></html>
"""
    try:
        components.html(html, height=1, width=1)
    except Exception:
        try:
            from streamlit_js_eval import streamlit_js_eval

            focus_js = json.dumps(focus_to)
            streamlit_js_eval(
                js_expressions=f"""
                (() => {{
                  const doc = window.parent?.document || document;
                  const key = {focus_js};
                  const roots = Array.from(doc.querySelectorAll('[class*="st-key-' + key + '"]'));
                  for (const root of roots) {{
                    const el = root.querySelector('input, [role="combobox"], textarea, select, canvas');
                    if (el) {{ el.focus?.(); return true; }}
                  }}
                  return false;
                }})()
                """,
                key=f"kb_focus_{component_key}",
            )
        except Exception:
            pass
