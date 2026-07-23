"""Dedicated arrow-key navigation for the Filters dialog.

Fixes Alternate phone → Payable balance radio → Apply / Clear all, and keeps
focus inside the dialog (no jump back to the browser window).
"""

from __future__ import annotations

import json

import streamlit.components.v1 as components


def inject_filters_chain_nav(
    *,
    chain: list[str],
    apply_key: str,
    clear_key: str,
    radio_key: str | None,
) -> None:
    """Install capture-phase arrow navigation for an open Filters dialog."""
    payload = {
        "chain": [str(k) for k in chain if k],
        "applyKey": apply_key,
        "clearKey": clear_key,
        "radioKey": radio_key or "",
    }
    data = json.dumps(payload).replace("</", "<\\/")
    html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;">
<script>
(function () {{
  const cfg = {data};
  const win = window.parent || window;
  const doc = win.document || document;
  const FLAG = '__vayFiltersChainNav';
  const HOLD = '__vayFiltersChainHold';

  function dialogRoot() {{
    try {{ return doc.querySelector('[role="dialog"]') || doc; }}
    catch (e) {{ return doc; }}
  }}

  function rootsFor(key) {{
    if (!key) return [];
    try {{
      const root = dialogRoot();
      const local = Array.from(root.querySelectorAll('[class*="st-key-' + key + '"]'));
      if (local.length) return local;
      return Array.from(doc.querySelectorAll('[class*="st-key-' + key + '"]'));
    }} catch (e) {{
      return [];
    }}
  }}

  function classKeys(node) {{
    const out = [];
    let cur = node;
    while (cur && cur !== doc.body) {{
      const cls = (cur.className && String(cur.className)) || '';
      const matches = cls.match(/st-key-[\\w-]+/g) || [];
      for (let i = 0; i < matches.length; i++) {{
        out.push(matches[i].slice('st-key-'.length));
      }}
      cur = cur.parentElement;
    }}
    return out;
  }}

  function inRadio() {{
    if (!cfg.radioKey) return false;
    const active = doc.activeElement;
    if (classKeys(active).indexOf(cfg.radioKey) >= 0) return true;
    const roots = rootsFor(cfg.radioKey);
    for (let i = 0; i < roots.length; i++) {{
      if (active && roots[i].contains(active)) return true;
    }}
    return false;
  }}

  function activeChainKey() {{
    const path = classKeys(doc.activeElement);
    for (let i = 0; i < path.length; i++) {{
      if (cfg.chain.indexOf(path[i]) >= 0) return path[i];
    }}
    if (cfg.radioKey && inRadio()) return cfg.radioKey;
    return null;
  }}

  function holdFocus(el) {{
    if (!el) return false;
    try {{
      if (win[HOLD]) {{ clearInterval(win[HOLD]); win[HOLD] = null; }}
    }} catch (e) {{}}
    const focusNow = function () {{
      try {{ el.focus({{ preventScroll: true }}); }}
      catch (e) {{ try {{ el.focus(); }} catch (e2) {{}} }}
    }};
    focusNow();
    let n = 0;
    win[HOLD] = setInterval(function () {{
      const root = dialogRoot();
      if (!root.contains(doc.activeElement)) focusNow();
      else if (doc.activeElement !== el && !el.contains(doc.activeElement)) focusNow();
      n += 1;
      if (n >= 15) {{
        try {{ clearInterval(win[HOLD]); }} catch (e) {{}}
        win[HOLD] = null;
      }}
    }}, 40);
    return true;
  }}

  function focusButton(key, label) {{
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const btn = roots[i].querySelector('button');
      if (btn) return holdFocus(btn);
    }}
    const want = String(label || '').trim().toLowerCase();
    const buttons = dialogRoot().querySelectorAll('button');
    for (let i = 0; i < buttons.length; i++) {{
      if (String(buttons[i].textContent || '').trim().toLowerCase() === want) {{
        return holdFocus(buttons[i]);
      }}
    }}
    return false;
  }}

  function focusRadio(key) {{
    const roots = rootsFor(key);
    for (let r = 0; r < roots.length; r++) {{
      const root = roots[r];
      const checked = root.querySelector(
        'input[type="radio"]:checked, [role="radio"][aria-checked="true"]'
      );
      const first = root.querySelector('input[type="radio"], [role="radio"]');
      const group = root.querySelector('[role="radiogroup"], [data-testid="stRadio"]');
      const label = root.querySelector('label');
      const candidates = [checked, first, group, label];
      for (let i = 0; i < candidates.length; i++) {{
        const el = candidates[i];
        if (!el) continue;
        try {{ if (el.tabIndex < 0) el.tabIndex = 0; }} catch (e) {{}}
        if (holdFocus(el)) return true;
      }}
      try {{
        if (label) {{ label.click(); return true; }}
        if (first) {{ first.click(); return true; }}
      }} catch (e) {{}}
    }}
    try {{
      const boxes = dialogRoot().querySelectorAll('[data-testid="stRadio"]');
      if (boxes.length) {{
        const box = boxes[boxes.length - 1];
        const el = box.querySelector(
          'input[type="radio"]:checked, [role="radio"], input[type="radio"], label'
        ) || box;
        try {{ if (el.tabIndex < 0) el.tabIndex = 0; }} catch (e) {{}}
        return holdFocus(el);
      }}
    }} catch (e) {{}}
    return false;
  }}

  function focusField(key) {{
    if (!key) return false;
    if (key === cfg.radioKey) return focusRadio(key);
    if (key === cfg.applyKey) return focusButton(key, 'Apply');
    if (key === cfg.clearKey) return focusButton(key, 'Clear all');
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const root = roots[i];
      const el = root.querySelector(
        'input:not([type="hidden"]), textarea, [role="combobox"], select, button'
      );
      if (el) return holdFocus(el);
    }}
    return false;
  }}

  function radioRoot() {{
    const roots = rootsFor(cfg.radioKey);
    if (roots.length) return roots[0];
    const boxes = dialogRoot().querySelectorAll('[data-testid="stRadio"]');
    return boxes.length ? boxes[boxes.length - 1] : null;
  }}

  function radioOptions() {{
    const root = radioRoot();
    if (!root) return [];
    // Streamlit renders each choice as a <label> — clicking the label selects it.
    let opts = Array.from(root.querySelectorAll('label'));
    if (opts.length) return opts;
    opts = Array.from(root.querySelectorAll('[role="radio"]'));
    if (opts.length) return opts;
    return Array.from(root.querySelectorAll('input[type="radio"]'));
  }}

  function selectRadioOption(el) {{
    if (!el) return false;
    try {{
      // Always resolve to the label Streamlit binds to the widget value.
      let label = el;
      if (!(label.tagName && label.tagName.toLowerCase() === 'label')) {{
        label = (el.closest && el.closest('label')) || el;
      }}
      const input = (label.matches && label.matches('input[type="radio"]'))
        ? label
        : (label.querySelector && label.querySelector('input[type="radio"]'));
      const roleRadio = (label.getAttribute && label.getAttribute('role') === 'radio')
        ? label
        : (label.querySelector && label.querySelector('[role="radio"]'));

      // Pause focus-hold so it cannot cancel the click.
      try {{
        if (win[HOLD]) {{ clearInterval(win[HOLD]); win[HOLD] = null; }}
      }} catch (e) {{}}

      if (input) {{
        try {{
          input.focus({{ preventScroll: true }});
        }} catch (e) {{
          try {{ input.focus(); }} catch (e2) {{}}
        }}
        input.checked = true;
        // Native click() is required for React/Streamlit to commit the value.
        input.click();
        try {{
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }} catch (e) {{}}
      }}
      if (roleRadio) {{
        try {{ roleRadio.setAttribute('aria-checked', 'true'); }} catch (e) {{}}
        try {{ roleRadio.click(); }} catch (e) {{}}
      }}
      try {{ label.click(); }} catch (e) {{}}

      // Keep the chosen option focused and visually selected.
      setTimeout(function () {{
        holdFocus(label);
      }}, 30);
      return true;
    }} catch (e) {{
      return false;
    }}
  }}

  // Track which option arrows highlighted (Enter commits this one).
  let highlightedRadioIndex = -1;

  function focusedRadioIndex(opts) {{
    if (highlightedRadioIndex >= 0 && highlightedRadioIndex < opts.length) {{
      return highlightedRadioIndex;
    }}
    const active = doc.activeElement;
    for (let i = 0; i < opts.length; i++) {{
      const o = opts[i];
      if (o === active || (o.contains && o.contains(active))) return i;
      if (o.getAttribute && o.getAttribute('aria-checked') === 'true') return i;
      const inp = o.querySelector && o.querySelector('input[type="radio"]');
      if ((inp && inp.checked) || o.checked) return i;
    }}
    return 0;
  }}

  function moveRadioHighlight(delta) {{
    const opts = radioOptions();
    if (!opts.length) return false;
    let i = focusedRadioIndex(opts);
    i = (i + delta + opts.length) % opts.length;
    highlightedRadioIndex = i;
    // Select as you move so the chosen option is always displayed.
    return selectRadioOption(opts[i]);
  }}

  function commitHighlightedRadio() {{
    const opts = radioOptions();
    if (!opts.length) return false;
    const i = focusedRadioIndex(opts);
    highlightedRadioIndex = i;
    return selectRadioOption(opts[i]);
  }}

  function onKeyDown(ev) {{
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const dialog = doc.querySelector('[role="dialog"]');
    if (!dialog) return;

    const isDown = ev.key === 'ArrowDown';
    const isUp = ev.key === 'ArrowUp';
    const isLeft = ev.key === 'ArrowLeft';
    const isRight = ev.key === 'ArrowRight';
    const isEnter = ev.key === 'Enter';
    if (!isDown && !isUp && !isLeft && !isRight && !isEnter) return;

    const active = doc.activeElement;
    if (active && !dialog.contains(active) && !inRadio()) return;

    const key = activeChainKey();
    const onRadio = !!(cfg.radioKey && (key === cfg.radioKey || inRadio()));
    const idx = key ? cfg.chain.indexOf(key) : -1;

    if (onRadio) {{
      // Left/Right (and Up within the group): move between radio options.
      // Stop other handlers so focus does not jump back to Alternate phone.
      if (isEnter) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        // Defer past keydown so Streamlit/React accepts the synthetic click.
        setTimeout(function () {{ commitHighlightedRadio(); }}, 0);
        return;
      }}
      if (isLeft || isRight) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        const delta = isRight ? 1 : -1;
        setTimeout(function () {{ moveRadioHighlight(delta); }}, 0);
        return;
      }}
      if (isDown) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        focusButton(cfg.applyKey, 'Apply');
        return;
      }}
      if (isUp) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        if (idx > 0) focusField(cfg.chain[idx - 1]);
        return;
      }}
    }}

    if (key === cfg.applyKey || key === cfg.clearKey) {{
      if (isLeft && key === cfg.applyKey) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        focusButton(cfg.clearKey, 'Clear all');
        return;
      }}
      if (isRight && key === cfg.clearKey) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        focusButton(cfg.applyKey, 'Apply');
        return;
      }}
      if (isUp) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        if (cfg.radioKey) focusRadio(cfg.radioKey);
        else if (idx > 0) focusField(cfg.chain[idx - 1]);
        return;
      }}
      if (isDown) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        return;
      }}
    }}

    if ((isDown || isUp) && idx >= 0) {{
      let n = active;
      let selectOpen = false;
      while (n && n !== doc.body) {{
        if (n.getAttribute && n.getAttribute('aria-expanded') === 'true') {{
          selectOpen = true;
          break;
        }}
        n = n.parentElement;
      }}
      if (selectOpen && key !== cfg.radioKey) return;

      const nextIdx = isDown ? idx + 1 : idx - 1;
      if (nextIdx < 0 || nextIdx >= cfg.chain.length) return;
      ev.preventDefault();
      ev.stopPropagation();
      try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
      focusField(cfg.chain[nextIdx]);
    }}
  }}

  try {{
    if (win[FLAG]) {{
      doc.removeEventListener('keydown', win[FLAG], true);
      win.removeEventListener('keydown', win[FLAG], true);
    }}
    if (win.__vayFilterRadioKeyboard) {{
      doc.removeEventListener('keydown', win.__vayFilterRadioKeyboard, true);
      win.removeEventListener('keydown', win.__vayFilterRadioKeyboard, true);
      win.__vayFilterRadioKeyboard = null;
    }}
    if (win.__vayFilterLastFieldExit) {{
      doc.removeEventListener('keydown', win.__vayFilterLastFieldExit, true);
      win.removeEventListener('keydown', win.__vayFilterLastFieldExit, true);
      win.__vayFilterLastFieldExit = null;
    }}
  }} catch (e) {{}}
  win[FLAG] = onKeyDown;
  win.addEventListener('keydown', onKeyDown, true);
  doc.addEventListener('keydown', onKeyDown, true);
}})();
</script>
</body></html>
"""
    try:
        components.html(html, height=1, width=1)
    except Exception:
        pass
