"""Shared Filters / Sort dialog keyboard navigation.

Behaviour (plan):
- Tab / Shift+Tab: never intercepted.
- Open select menus are fully native: arrows highlight, Enter picks the option
  (single- and multi-select dropdowns alike).
- Up / Down: move between dialog chain fields.
- Enter on a closed dropdown / text field: Apply.
- Left / Right inside a radiogroup (Sort direction): native Baseweb move+select.
- Enter on a radio: select the focused option, then Apply on the next Enter.
- Space: never intercepted (native radio select).
"""

from __future__ import annotations

import json

from vaybooks.bms.ui.html_iframe import inject_html


def inject_filters_chain_nav(
    *,
    chain: list[str],
    apply_key: str,
    clear_key: str | None = None,
    radio_key: str | None = None,
    radio_keys: list[str] | None = None,
) -> None:
    """Install capture-phase keyboard handling for Filters / Sort dialogs."""
    keys = [str(k) for k in (radio_keys or []) if k]
    if not keys and radio_key:
        keys = [str(radio_key)]
    primary = keys[-1] if keys else (str(radio_key) if radio_key else "")
    payload = {
        "chain": [str(k) for k in chain if k],
        "applyKey": apply_key,
        "clearKey": clear_key or "",
        "radioKey": primary,
        "radioKeys": keys,
        "version": "field-nav-enter-v4",
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
  const STYLE_ID = '__vayFilterRadioFocusStyle';
  const SNAP = '__vayDialogChoiceSnap';

  if (!win[SNAP]) win[SNAP] = {{}};

  function radioKeyList() {{
    if (cfg.radioKeys && cfg.radioKeys.length) return cfg.radioKeys;
    return cfg.radioKey ? [cfg.radioKey] : [];
  }}

  function ensureFocusStyles() {{
    // Do NOT outline inputs / comboboxes / Baseweb select children. That rule
    // leaked into every dialog and painted a thick blue bar on the focused
    // search caret inside dropdowns (e.g. Create Purchase Order → Vendor).
    // Only keep a visible ring for Sort-direction radios.
    try {{
      const old = doc.getElementById(STYLE_ID);
      if (old) old.remove();
      const style = doc.createElement('style');
      style.id = STYLE_ID;
      style.textContent = [
        '[role="dialog"] [data-testid="stRadio"] label[data-baseweb="radio"]:focus-within,',
        '[role="dialog"] [data-testid="stRadio"] input[type="radio"]:focus-visible {{',
        '  outline: 2px solid #1c64f2 !important;',
        '  outline-offset: 2px !important;',
        '  box-shadow: 0 0 0 2px rgba(28, 100, 242, 0.35) !important;',
        '}}'
      ].join('\\n');
      (doc.head || doc.documentElement).appendChild(style);
    }} catch (e) {{}}
  }}

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

  function activeChainKey() {{
    const path = classKeys(doc.activeElement);
    for (let i = 0; i < path.length; i++) {{
      if (cfg.chain.indexOf(path[i]) >= 0) return path[i];
    }}
    return null;
  }}

  function inRadio() {{
    const active = doc.activeElement;
    if (!active) return false;
    const keys = radioKeyList();
    const path = classKeys(active);
    for (let i = 0; i < path.length; i++) {{
      if (keys.indexOf(path[i]) >= 0) return true;
    }}
    const dialog = dialogRoot();
    if (!dialog || !dialog.contains(active)) return false;
    let n = active;
    while (n && n !== dialog) {{
      if (n.getAttribute && (
        n.getAttribute('role') === 'radiogroup'
        || n.getAttribute('data-testid') === 'stRadio'
        || (n.tagName && n.tagName.toLowerCase() === 'input'
            && String(n.type || '').toLowerCase() === 'radio')
      )) return true;
      n = n.parentElement;
    }}
    return false;
  }}

  function selectOpen(el) {{
    let n = el;
    while (n && n !== doc.body) {{
      if (n.getAttribute && n.getAttribute('aria-expanded') === 'true') return true;
      n = n.parentElement;
    }}
    // Baseweb renders the option list in a portal outside the input.
    try {{
      const pop = doc.querySelector(
        '[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] [role="listbox"]'
      );
      if (pop && pop.offsetParent !== null) return true;
    }} catch (e) {{}}
    return false;
  }}

  function softFocus(el) {{
    if (!el) return false;
    try {{ el.focus({{ preventScroll: true }}); }}
    catch (e) {{ try {{ el.focus(); }} catch (e2) {{}} }}
    return true;
  }}

  function focusButton(key, label) {{
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const btn = roots[i].querySelector('button');
      if (btn) return softFocus(btn);
    }}
    const want = String(label || '').trim().toLowerCase();
    const buttons = dialogRoot().querySelectorAll('button');
    for (let i = 0; i < buttons.length; i++) {{
      if (String(buttons[i].textContent || '').trim().toLowerCase() === want) {{
        return softFocus(buttons[i]);
      }}
    }}
    return false;
  }}

  function focusRadioGroup(key) {{
    const roots = rootsFor(key);
    for (let r = 0; r < roots.length; r++) {{
      const root = roots[r];
      const checked = root.querySelector('input[type="radio"]:checked');
      const first = root.querySelector('input[type="radio"]');
      const el = checked || first;
      if (el) return softFocus(el);
    }}
    return false;
  }}

  function focusField(key) {{
    if (!key) return false;
    if (key === cfg.applyKey) {{
      return focusButton(key, 'Apply') || focusButton(key, 'Apply sort');
    }}
    if (cfg.clearKey && key === cfg.clearKey) {{
      return focusButton(key, 'Clear all');
    }}
    if (radioKeyList().indexOf(key) >= 0) return focusRadioGroup(key);
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const root = roots[i];
      const el = root.querySelector(
        'input:not([type="hidden"]):not([type="radio"]), textarea, [role="combobox"], select, button'
      );
      if (el) return softFocus(el);
      const radio = root.querySelector('input[type="radio"]:checked, input[type="radio"]');
      if (radio) return softFocus(radio);
    }}
    return false;
  }}

  function moveChain(delta) {{
    const key = activeChainKey();
    if (!key) return false;
    const idx = cfg.chain.indexOf(key);
    if (idx < 0) return false;
    const next = idx + delta;
    if (next < 0 || next >= cfg.chain.length) return false;
    return focusField(cfg.chain[next]);
  }}

  function clickApply() {{
    const roots = rootsFor(cfg.applyKey);
    for (let i = 0; i < roots.length; i++) {{
      const btn = roots[i].querySelector('button');
      if (btn) {{ btn.click(); return true; }}
    }}
    const labels = ['apply', 'apply sort'];
    const buttons = dialogRoot().querySelectorAll('button');
    for (let i = 0; i < buttons.length; i++) {{
      const t = String(buttons[i].textContent || '').trim().toLowerCase();
      if (labels.indexOf(t) >= 0) {{ buttons[i].click(); return true; }}
    }}
    return false;
  }}

  function currentRadioValue() {{
    const active = doc.activeElement;
    if (!active) return '';
    let input = null;
    if (active.matches && active.matches('input[type="radio"]')) input = active;
    else {{
      const lab = active.closest && active.closest('label');
      input = lab && lab.querySelector && lab.querySelector('input[type="radio"]');
    }}
    if (!input) {{
      const group = active.closest && active.closest('[role="radiogroup"], [data-testid="stRadio"]');
      input = group && group.querySelector('input[type="radio"]:checked');
    }}
    return input ? String(input.value) : '';
  }}

  function selectFocusedRadio() {{
    const active = doc.activeElement;
    if (!active) return false;
    try {{
      let input = null;
      let label = null;
      if (active.matches && active.matches('input[type="radio"]')) {{
        input = active;
        label = active.closest && active.closest('label[data-baseweb="radio"], label');
      }} else if (active.closest) {{
        label = active.closest('label[data-baseweb="radio"], label');
        input = label && label.querySelector && label.querySelector('input[type="radio"]');
      }}
      if (label) {{ label.click(); return true; }}
      if (input) {{
        input.checked = true;
        input.click();
        return true;
      }}
    }} catch (e) {{}}
    return false;
  }}

  function widgetSnapKey() {{
    return activeChainKey() || (inRadio() ? (radioKeyList()[0] || 'radio') : '');
  }}

  function readChoiceValue() {{
    if (inRadio()) return currentRadioValue();
    const active = doc.activeElement;
    if (!active) return '';
    // Closed Baseweb select / combobox: use visible value text.
    const combo = active.closest && active.closest('[data-baseweb="select"], [role="combobox"]');
    if (combo) {{
      const val = combo.querySelector('[data-baseweb="select"] span, [aria-selected="true"], input');
      if (val) return String(val.textContent || val.value || '').trim();
    }}
    if (active.tagName && active.tagName.toLowerCase() === 'input') {{
      return String(active.value || '');
    }}
    return String(active.textContent || '').trim().slice(0, 120);
  }}

  function isTextish(el) {{
    if (!el) return false;
    const t = (el.tagName || '').toLowerCase();
    const inputType = (el.type && String(el.type).toLowerCase()) || '';
    if (t === 'textarea') return true;
    if (t === 'input' && (
      !inputType || inputType === 'text' || inputType === 'search'
      || inputType === 'email' || inputType === 'tel' || inputType === 'url'
      || inputType === 'password' || inputType === 'number'
    )) return true;
    return false;
  }}

  function isChoiceControl() {{
    if (inRadio()) return true;
    const active = doc.activeElement;
    if (!active) return false;
    if (active.closest && active.closest('[data-baseweb="select"], [role="combobox"], [data-testid="stSelectbox"]')) {{
      return true;
    }}
    return false;
  }}

  function onKeyDown(ev) {{
    if (ev.key === 'Tab') return;
    if (ev.key === ' ') return;
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;

    const dialog = doc.querySelector('[role="dialog"]');
    if (!dialog) return;
    const active = doc.activeElement;
    if (active && !dialog.contains(active) && !inRadio()) return;

    const isDown = ev.key === 'ArrowDown';
    const isUp = ev.key === 'ArrowUp';
    const isLeft = ev.key === 'ArrowLeft';
    const isRight = ev.key === 'ArrowRight';
    const isEnter = ev.key === 'Enter';

    // Left/Right on radio: native Baseweb — do not preventDefault.
    if ((isLeft || isRight) && inRadio()) return;

    // Open dropdown menu: fully native (arrows highlight, Enter picks).
    if (selectOpen(active)) return;

    // Up/Down move between chain fields (including when focus is on a radio).
    if (isDown || isUp) {{
      const key = activeChainKey();
      if (!key && !inRadio()) return;
      ev.preventDefault();
      ev.stopPropagation();
      try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
      setTimeout(function () {{ moveChain(isDown ? 1 : -1); }}, 0);
      return;
    }}

    if (!isEnter) return;
    if (ev.shiftKey) return;

    // Apply / Clear buttons: native activation.
    const key = activeChainKey();
    if (key === cfg.applyKey || (cfg.clearKey && key === cfg.clearKey)) return;

    // Radio (Sort direction): two-step Enter — select, then Apply.
    if (inRadio()) {{
      ev.preventDefault();
      ev.stopPropagation();
      try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
      const snapKey = widgetSnapKey();
      const now = readChoiceValue();
      const prev = win[SNAP][snapKey];
      setTimeout(function () {{
        if (prev === undefined || prev !== now || !document.querySelector(
          '[role="dialog"] input[type="radio"]:checked'
        )) {{
          selectFocusedRadio();
          win[SNAP][snapKey] = currentRadioValue() || now;
          return;
        }}
        // Already committed — Apply.
        clickApply();
      }}, 0);
      return;
    }}

    // Closed dropdown: Enter applies (the menu was never opened).
    if (isChoiceControl()) {{
      ev.preventDefault();
      ev.stopPropagation();
      try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
      setTimeout(function () {{ clickApply(); }}, 0);
      return;
    }}

    // Text and other fields: Enter applies.
    if (isTextish(active) || key) {{
      ev.preventDefault();
      ev.stopPropagation();
      try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
      setTimeout(function () {{ clickApply(); }}, 0);
    }}
  }}

  // Snapshot choice values when focus enters a choice widget.
  function onFocusIn(ev) {{
    const dialog = doc.querySelector('[role="dialog"]');
    if (!dialog || !dialog.contains(ev.target)) return;
    const prevActive = doc.activeElement;
    // Defer so activeElement is updated.
    setTimeout(function () {{
      if (!inRadio() && !isChoiceControl()) return;
      const snapKey = widgetSnapKey();
      if (!snapKey) return;
      if (win[SNAP][snapKey] === undefined) {{
        win[SNAP][snapKey] = readChoiceValue();
      }}
    }}, 0);
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
    if (win.__vayFiltersChainHold) {{
      try {{ clearInterval(win.__vayFiltersChainHold); }} catch (e) {{}}
      win.__vayFiltersChainHold = null;
    }}
    if (win.__vayDialogChoiceFocusIn) {{
      doc.removeEventListener('focusin', win.__vayDialogChoiceFocusIn, true);
      win.__vayDialogChoiceFocusIn = null;
    }}
  }} catch (e) {{}}

  try {{
    const old = doc.getElementById(STYLE_ID);
    if (old) old.remove();
  }} catch (e) {{}}
  ensureFocusStyles();
  win[FLAG] = onKeyDown;
  win.__vayDialogChoiceFocusIn = onFocusIn;
  win.addEventListener('keydown', onKeyDown, true);
  doc.addEventListener('keydown', onKeyDown, true);
  doc.addEventListener('focusin', onFocusIn, true);
}})();
</script>
</body></html>
"""
    try:
        inject_html(html, height=1, width=1)
    except Exception:
        pass
