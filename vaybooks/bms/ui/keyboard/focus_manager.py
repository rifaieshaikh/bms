"""Programmatic focus trail across keyed Streamlit widgets.

Enter advances along ``chain`` (e.g. Vendor → Expected → Product → Qty → Rate…).
ArrowLeft / ArrowRight only move within Product / Qty / Rate grid cells.
ArrowUp / ArrowDown move within a column, with optional header/footer edges.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence

import streamlit.components.v1 as components


def inject_focus_manager(
    chain: Sequence[str],
    *,
    initial_key: str | None = None,
    restore_key: str | None = None,
    add_line_key: str | None = None,
    data_editor_key: str | None = None,
    columns: Mapping[str, Sequence[str]] | None = None,
    above_first: str | None = None,
    below_last: str | None = None,
    component_key: str = "focus_mgr",
    mode: str = "form",
    apply_key: str | None = None,
) -> None:
    """Focus ``restore_key`` when set; traverse with Enter and arrows.

    Modes:
    - ``form`` (default, PO lines): Enter advances; arrows use grid rules
    - ``linear_apply`` (filter/sort dialogs): Tab/arrows move along ``chain``;
      Enter clicks ``apply_key``

    Form mode details:
    - Enter → next widget in ``chain`` (Vendor → Expected → Product…)
    - ArrowLeft / ArrowRight → previous/next **grid** cell only (not Vendor/Expected)
    - ArrowUp / ArrowDown → same column previous/next row when ``columns`` set
    - ArrowUp on first Product/Qty/Rate → ``above_first`` (e.g. Expected)
    - ArrowDown on last row → ``below_last`` (e.g. Save)
    - Arrows on ``above_first`` (Expected date) are left alone for the date picker;
      use Enter to move Expected → Product
    - Auto-focus runs only when ``restore_key`` is provided (avoids stealing focus
      after line-item remounts)
    - Open selectbox lists are left alone (arrows move the highlight)
    """
    safe_chain = [str(k) for k in chain if k]
    if not safe_chain and not data_editor_key:
        return
    # Only restore when explicitly requested — never fall back to initial on remount.
    focus_to = str(restore_key) if restore_key else ""
    _ = initial_key  # kept for call-site compatibility / first-open via restore_key
    col_payload = {
        "product": [str(k) for k in (columns or {}).get("product", []) if k],
        "qty": [str(k) for k in (columns or {}).get("qty", []) if k],
        "rate": [str(k) for k in (columns or {}).get("rate", []) if k],
    }
    payload = {
        "chain": safe_chain,
        "focusTo": focus_to,
        "addLineKey": add_line_key or "",
        "dataEditorKey": data_editor_key or "",
        "columns": col_payload,
        "aboveFirst": above_first or "",
        "belowLast": below_last or "",
        "mode": str(mode or "form"),
        "applyKey": str(apply_key or ""),
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
      'button:not([disabled])',
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
          const x = rect.left + Math.min(48, Math.max(24, rect.width * 0.08));
          const y = rect.top + Math.min(52, Math.max(36, rect.height * 0.12));
          const hit = doc.elementFromPoint(x, y) || canvas;
          fireAt(hit, x, y);
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

  function retreatFrom(key) {{
    const c = win.__vayFocusMgrCfg || cfg;
    const idx = c.chain.indexOf(key);
    if (idx <= 0) return;
    focusKey(c.chain[idx - 1]);
  }}

  function findColumn(key) {{
    const c = win.__vayFocusMgrCfg || cfg;
    const cols = c.columns || {{}};
    const names = ['product', 'qty', 'rate'];
    for (let i = 0; i < names.length; i++) {{
      const name = names[i];
      const list = cols[name] || [];
      const idx = list.indexOf(key);
      if (idx >= 0) return {{ name: name, list: list, index: idx }};
    }}
    return null;
  }}

  function gridChain() {{
    const c = win.__vayFocusMgrCfg || cfg;
    const cols = c.columns || {{}};
    const products = cols.product || [];
    const qtys = cols.qty || [];
    const rates = cols.rate || [];
    const out = [];
    const n = Math.max(products.length, qtys.length, rates.length);
    for (let i = 0; i < n; i++) {{
      if (products[i]) out.push(products[i]);
      if (qtys[i]) out.push(qtys[i]);
      if (rates[i]) out.push(rates[i]);
    }}
    return out;
  }}

  function advanceInGrid(key) {{
    const g = gridChain();
    const idx = g.indexOf(key);
    if (idx < 0 || idx >= g.length - 1) return;
    focusKey(g[idx + 1]);
  }}

  function retreatInGrid(key) {{
    const g = gridChain();
    const idx = g.indexOf(key);
    if (idx <= 0) return;
    focusKey(g[idx - 1]);
  }}

  function moveVertical(key, direction) {{
    const c = win.__vayFocusMgrCfg || cfg;
    // Do not intercept arrows on aboveFirst (Expected date) — native date picker uses them.
    if (c.aboveFirst && key === c.aboveFirst) return false;

    if (c.belowLast && key === c.belowLast && direction < 0) {{
      const products = (c.columns && c.columns.product) || [];
      if (products.length) focusKey(products[products.length - 1]);
      return true;
    }}

    const hit = findColumn(key);
    if (!hit) return false;
    const next = hit.index + direction;
    if (next < 0) {{
      if (c.aboveFirst) {{
        focusKey(c.aboveFirst);
        return true;
      }}
      return true;
    }}
    if (next >= hit.list.length) {{
      if (c.belowLast) {{
        focusKey(c.belowLast);
        return true;
      }}
      return true;
    }}
    focusKey(hit.list[next]);
    return true;
  }}

  function onKeyDown(ev) {{
    const isEnter = ev.key === 'Enter';
    const isRight = ev.key === 'ArrowRight';
    const isLeft = ev.key === 'ArrowLeft';
    const isUp = ev.key === 'ArrowUp';
    const isDown = ev.key === 'ArrowDown';
    const isTab = ev.key === 'Tab';
    const c = win.__vayFocusMgrCfg || cfg;
    const linear = c.mode === 'linear_apply';

    if (linear) {{
      if (!isEnter && !isRight && !isLeft && !isUp && !isDown && !isTab) return;
      if ((isEnter || isRight || isLeft || isUp || isDown) &&
          (ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) return;
      if (isTab && (ev.ctrlKey || ev.metaKey || ev.altKey)) return;
    }} else {{
      if (!isEnter && !isRight && !isLeft && !isUp && !isDown) return;
      if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey) return;
    }}

    const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toLowerCase() : '';
    if (tag === 'textarea') return;
    if (listOpen(ev.target)) return;

    if (!linear && (nodeInsideDataEditor(ev.target) || nodeInsideDataEditor(doc.activeElement))) {{
      if (!isEnter) return;
      setTimeout(function () {{
        if (listOpen(doc.activeElement)) return;
        sendTab(doc.activeElement);
      }}, 10);
      return;
    }}

    const key = activeKey();
    if (!key) return;

    const inChain = c.chain.indexOf(key) >= 0;
    const onBelowLast = !!(c.belowLast && key === c.belowLast);
    const inGrid = !!findColumn(key);

    // Filter/sort dialogs: linear chain nav; Enter applies.
    if (linear) {{
      if (!inChain) return;
      if (isEnter) {{
        // Text / number inputs: let Streamlit (and st.form) handle Enter so the
        // typed value is committed with the submit. Intercepting Enter here
        // used to Apply with a stale empty string.
        const t = (ev.target && ev.target.tagName)
          ? ev.target.tagName.toLowerCase() : '';
        const inputType = (ev.target && ev.target.type)
          ? String(ev.target.type).toLowerCase() : '';
        const textish = (
          t === 'textarea'
          || (t === 'input' && (
            !inputType
            || inputType === 'text'
            || inputType === 'search'
            || inputType === 'email'
            || inputType === 'tel'
            || inputType === 'url'
            || inputType === 'password'
            || inputType === 'number'
          ))
          || (ev.target && ev.target.getAttribute
              && ev.target.getAttribute('contenteditable') === 'true')
        );
        if (textish) return;

        ev.preventDefault();
        ev.stopPropagation();
        setTimeout(function () {{
          if (c.applyKey) clickKey(c.applyKey);
        }}, 0);
        return;
      }}
      const forward = isDown || isRight || (isTab && !ev.shiftKey);
      const backward = isUp || isLeft || (isTab && ev.shiftKey);
      if (!forward && !backward) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (forward) {{
        setTimeout(function () {{ advanceFrom(key); }}, 0);
      }} else {{
        setTimeout(function () {{ retreatFrom(key); }}, 0);
      }}
      return;
    }}

    // Vertical: grid columns, or Up from Save. Never steal arrows from Expected date.
    if (isUp || isDown) {{
      if (!inGrid && !onBelowLast) return;
      const handled = moveVertical(key, isDown ? 1 : -1);
      if (handled) {{
        ev.preventDefault();
        ev.stopPropagation();
      }}
      return;
    }}

    // Horizontal arrows: Product / Qty / Rate only — never Vendor ↔ Expected.
    if (isLeft || isRight) {{
      if (!inGrid) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (isLeft) {{
        setTimeout(function () {{ retreatInGrid(key); }}, 0);
      }} else {{
        setTimeout(function () {{ advanceInGrid(key); }}, 0);
      }}
      return;
    }}

    // Enter: full chain (Vendor → Expected → Product → … → Save).
    if (isEnter) {{
      if (!inChain) return;
      ev.preventDefault();
      ev.stopPropagation();
      setTimeout(function () {{ advanceFrom(key); }}, 0);
    }}
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
  if (cfg.focusTo) {{
    tryFocus();
    setTimeout(tryFocus, 40);
    setTimeout(tryFocus, 120);
    setTimeout(tryFocus, 280);
    setTimeout(tryFocus, 500);
  }}
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
                    const el = root.querySelector('input, [role="combobox"], textarea, select, canvas, button');
                    if (el) {{ el.focus?.(); return true; }}
                  }}
                  return false;
                }})()
                """,
                key=f"kb_focus_{component_key}",
            )
        except Exception:
            pass
