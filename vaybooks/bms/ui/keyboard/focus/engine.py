"""Thin shared focus engine: per-manager_id registry, rules-driven key routing."""

from __future__ import annotations

import json
from typing import Any

import streamlit.components.v1 as components

from vaybooks.bms.ui.keyboard.focus.base import FocusConfig


def inject_focus_engine(config: FocusConfig) -> None:
    """Register ``config`` under ``manager_id`` and attach document listeners."""
    safe_chain = [str(k) for k in config.chain if k]
    if not safe_chain and not config.data_editor_key:
        return

    rules = dict(config.rules or {})
    mode = str(rules.get("mode") or "purchase_lines")
    # Back-compat alias used by older call sites / tests.
    if mode == "form":
        mode = "purchase_lines"
        rules["mode"] = mode

    col_payload = {
        "product": [str(k) for k in (config.columns or {}).get("product", []) if k],
        "qty": [str(k) for k in (config.columns or {}).get("qty", []) if k],
        "rate": [str(k) for k in (config.columns or {}).get("rate", []) if k],
    }
    apply_key = str(rules.get("apply_key") or "")
    clear_key = str(rules.get("clear_key") or "")
    last_field_key = str(rules.get("last_field_key") or "")
    payload: dict[str, Any] = {
        "managerId": str(config.manager_id),
        "chain": safe_chain,
        "focusTo": str(config.restore_key) if config.restore_key else "",
        "addLineKey": config.add_line_key or "",
        "dataEditorKey": config.data_editor_key or "",
        "columns": col_payload,
        "aboveFirst": config.above_first or "",
        "belowLast": config.below_last or "",
        "mode": mode,
        "applyKey": apply_key,
        "clearKey": clear_key,
        "lastFieldKey": last_field_key,
        "rules": rules,
        "nonce": str(config.component_key),
    }
    data = json.dumps(payload).replace("</", "<\\/")
    html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;">
<script>
(function () {{
  const cfg = {data};
  const win = window.parent || window;
  const doc = win.document || document;

  if (!win.__vayFocusMgrById) win.__vayFocusMgrById = {{}};
  win.__vayFocusMgrById[cfg.managerId] = cfg;
  win.__vayFocusMgrActiveId = cfg.managerId;

  function rulesOf(c) {{
    return (c && c.rules) ? c.rules : {{}};
  }}

  function gridRoles(c) {{
    const r = rulesOf(c).grid_roles;
    if (Array.isArray(r) && r.length) return r;
    return ['product', 'qty', 'rate'];
  }}

  function keyInManager(c, key) {{
    if (!c || !key) return false;
    if ((c.chain || []).indexOf(key) >= 0) return true;
    const cols = c.columns || {{}};
    const names = gridRoles(c);
    for (let i = 0; i < names.length; i++) {{
      if ((cols[names[i]] || []).indexOf(key) >= 0) return true;
    }}
    return false;
  }}

  function resolveActiveCfg(focusedKey) {{
    const byId = win.__vayFocusMgrById || {{}};
    if (focusedKey) {{
      const ids = Object.keys(byId);
      for (let i = 0; i < ids.length; i++) {{
        const c = byId[ids[i]];
        if (keyInManager(c, focusedKey)) return c;
      }}
    }}
    const activeId = win.__vayFocusMgrActiveId;
    if (activeId && byId[activeId]) return byId[activeId];
    return cfg;
  }}

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
      'input[type="radio"]:not([disabled])',
      '[role="radio"]',
      'input:not([type="hidden"]):not([disabled])',
      'textarea:not([disabled])',
      'select:not([disabled])',
      '[role="combobox"]',
      '[role="radiogroup"]',
      '[contenteditable="true"]',
      'button:not([disabled])',
    ];
    for (const sel of selectors) {{
      const el = root.querySelector(sel);
      if (el) return el;
    }}
    return null;
  }}

  function isProductKey(key) {{
    return /_r[^_]+_product$/.test(String(key || ''));
  }}

  function focusKey(key) {{
    const roots = rootsFor(key);
    for (const root of roots) {{
      // Prefer an already-checked radio, else first radio / combobox / input.
      const checkedRadio = root.querySelector(
        'input[type="radio"]:checked, [role="radio"][aria-checked="true"]'
      );
      const anyRadio = root.querySelector(
        'input[type="radio"]:not([disabled]), [role="radio"]'
      );
      const combo = root.querySelector('[role="combobox"]');
      const el = checkedRadio || anyRadio || combo || focusable(root);
      if (!el) continue;
      try {{
        el.focus({{ preventScroll: false }});
        if (typeof el.select === 'function' && el.tagName === 'INPUT'
            && String(el.type || '').toLowerCase() !== 'radio') {{
          try {{ el.select(); }} catch (e) {{}}
        }}
        return true;
      }} catch (e) {{}}
    }}
    return false;
  }}

  function focusDialogButton(label) {{
    try {{
      const root = scopeRoot();
      const buttons = Array.from(root.querySelectorAll('button'));
      const want = String(label || '').trim().toLowerCase();
      for (let i = 0; i < buttons.length; i++) {{
        const text = String(buttons[i].textContent || '').trim().toLowerCase();
        if (text === want) {{
          buttons[i].focus({{ preventScroll: false }});
          return true;
        }}
      }}
    }} catch (e) {{}}
    return false;
  }}

  function focusAction(key, fallbackLabel) {{
    if (key && focusKey(key)) return true;
    if (fallbackLabel) return focusDialogButton(fallbackLabel);
    return false;
  }}

  function datePickerOpen() {{
    try {{
      if (doc.querySelector('[data-baseweb="calendar"]')) return true;
      const pops = doc.querySelectorAll('[data-baseweb="popover"]');
      for (let i = 0; i < pops.length; i++) {{
        if (pops[i].querySelector('[data-baseweb="calendar"], [role="grid"]')) return true;
      }}
    }} catch (e) {{}}
    return false;
  }}

  function nodeInDateCalendar(node) {{
    let cur = node;
    while (cur && cur !== doc.body) {{
      try {{
        const db = cur.getAttribute && cur.getAttribute('data-baseweb');
        if (db === 'calendar') return true;
        if (db === 'popover' && cur.querySelector('[data-baseweb="calendar"]')) return true;
        if (cur.getAttribute && cur.getAttribute('role') === 'grid' && datePickerOpen()) {{
          return true;
        }}
      }} catch (e) {{}}
      cur = cur.parentElement;
    }}
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

  function closeOpenDatePickers() {{
    if (!datePickerOpen()) return;
    try {{
      const active = doc.activeElement;
      if (active && typeof active.blur === 'function') {{
        try {{ active.blur(); }} catch (e) {{}}
      }}
      const cal = doc.querySelector('[data-baseweb="calendar"]');
      const dialog = doc.querySelector('[role="dialog"]');
      const clickTarget = dialog || doc.body;
      if (clickTarget) {{
        const rect = clickTarget.getBoundingClientRect();
        const calRect = cal ? cal.getBoundingClientRect() : null;
        let x = rect.left + Math.min(24, Math.max(8, rect.width * 0.05));
        let y = rect.top + Math.min(24, Math.max(8, rect.height * 0.05));
        if (calRect && x >= calRect.left && x <= calRect.right &&
            y >= calRect.top && y <= calRect.bottom) {{
          x = rect.left + 4;
          y = rect.bottom - 4;
        }}
        fireAt(clickTarget, x, y);
      }}
      if (datePickerOpen()) {{
        const opts = {{
          key: 'Escape', code: 'Escape', keyCode: 27, which: 27,
          bubbles: true, cancelable: true, view: win
        }};
        const target = cal || active || doc.body;
        try {{
          target.dispatchEvent(new KeyboardEvent('keydown', opts));
          target.dispatchEvent(new KeyboardEvent('keyup', opts));
        }} catch (e) {{}}
      }}
    }} catch (e) {{}}
  }}

  function isActionButtonKey(key) {{
    if (!key) return false;
    if (/_(save|cancel|confirm)$/.test(String(key))) return true;
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const root = roots[i];
      const field = root.querySelector(
        'input:not([type="hidden"]), textarea, select, [role="combobox"]'
      );
      if (field) return false;
      if (root.querySelector('button')) return true;
    }}
    return false;
  }}

  function productHasSelection(key) {{
    const roots = rootsFor(key);
    for (let i = 0; i < roots.length; i++) {{
      const root = roots[i];
      if (root.querySelector('[data-baseweb="tag"]')) return true;
      if (root.querySelector(
        '[aria-label="Clear value"], [title="Clear value"], [aria-label="Clear all"]'
      )) return true;
      if (root.querySelector('[data-baseweb="placeholder"]')) return false;
      const select = root.querySelector('[data-baseweb="select"]');
      if (select) {{
        const text = String(select.textContent || '').trim();
        if (!text || /^search product/i.test(text) || /^search /i.test(text)) {{
          return false;
        }}
        return true;
      }}
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

  function classKeysOnPath(start) {{
    const out = [];
    let node = start;
    while (node && node !== doc.body) {{
      const cls = (node.className && String(node.className)) || '';
      const matches = cls.match(/st-key-[\\w-]+/g) || [];
      for (let i = 0; i < matches.length; i++) {{
        out.push(matches[i].slice('st-key-'.length));
      }}
      node = node.parentElement;
    }}
    return out;
  }}

  function activeKey() {{
    const active = doc.activeElement;
    if (!active) return null;
    const pathKeys = classKeysOnPath(active);
    // Prefer a key that belongs to the active focus manager chain.
    try {{
      const byId = win.__vayFocusMgrById || {{}};
      const activeId = win.__vayFocusMgrActiveId;
      const preferred = (activeId && byId[activeId]) ? byId[activeId] : null;
      if (preferred && preferred.chain && preferred.chain.length) {{
        for (let i = 0; i < pathKeys.length; i++) {{
          if (preferred.chain.indexOf(pathKeys[i]) >= 0) return pathKeys[i];
        }}
      }}
      const ids = Object.keys(byId);
      for (let i = 0; i < pathKeys.length; i++) {{
        for (let j = 0; j < ids.length; j++) {{
          const c = byId[ids[j]];
          if (c && c.chain && c.chain.indexOf(pathKeys[i]) >= 0) return pathKeys[i];
        }}
      }}
    }} catch (e) {{}}
    if (pathKeys.length) {{
      // Fall back to longest key on the path (most specific widget).
      let best = pathKeys[0];
      for (let i = 1; i < pathKeys.length; i++) {{
        if (pathKeys[i].length > best.length) best = pathKeys[i];
      }}
      return best;
    }}
    // Listbox options are often portaled outside the widget; resolve via the
    // expanded combobox that owns the open list.
    try {{
      const expanded = doc.querySelector(
        '[aria-expanded="true"][role="combobox"], [aria-expanded="true"]'
      );
      const expandedKeys = classKeysOnPath(expanded);
      if (expandedKeys.length) return expandedKeys[0];
    }} catch (e) {{}}
    return null;
  }}

  function listOpen(el) {{
    if (!el) return false;
    let node = el;
    while (node && node !== doc.body) {{
      if (node.getAttribute && node.getAttribute('aria-expanded') === 'true') return true;
      node = node.parentElement;
    }}
    // Avoid false positives from stale popovers belonging to other widgets.
    try {{
      const active = doc.activeElement || el;
      const expanded = active.closest
        ? active.closest('[aria-expanded="true"]')
        : null;
      if (!expanded) return false;
      const pop = doc.querySelector('[data-baseweb="popover"] [role="listbox"]');
      if (pop && pop.offsetParent !== null) return true;
    }} catch (e) {{}}
    return false;
  }}

  function closeOpenLists() {{
    try {{
      const opts = {{
        key: 'Escape', code: 'Escape', keyCode: 27, which: 27,
        bubbles: true, cancelable: true, view: win
      }};
      const target = doc.activeElement || doc.body;
      target.dispatchEvent(new KeyboardEvent('keydown', opts));
      target.dispatchEvent(new KeyboardEvent('keyup', opts));
    }} catch (e) {{}}
  }}

  function linearButtonPair(c, r) {{
    const applyKey = c.applyKey || r.apply_key || '';
    const clearKey = c.clearKey || r.clear_key || '';
    const explicitLast = c.lastFieldKey || r.last_field_key || '';
    if (!applyKey || !clearKey || !(c.chain || []).length) {{
      return {{
        applyKey: applyKey || '',
        clearKey: clearKey || '',
        lastFieldKey: explicitLast || '',
        lastFieldIdx: -1,
      }};
    }}
    let lastFieldIdx = -1;
    if (explicitLast) {{
      lastFieldIdx = c.chain.indexOf(explicitLast);
    }}
    if (lastFieldIdx < 0) {{
      const clearIdx = c.chain.indexOf(clearKey);
      const applyIdx = c.chain.indexOf(applyKey);
      const buttonStart = Math.min(
        clearIdx >= 0 ? clearIdx : c.chain.length,
        applyIdx >= 0 ? applyIdx : c.chain.length
      );
      lastFieldIdx = buttonStart - 1;
    }}
    const lastFieldKey = lastFieldIdx >= 0 ? c.chain[lastFieldIdx] : explicitLast;
    return {{
      applyKey: applyKey,
      clearKey: clearKey,
      lastFieldKey: lastFieldKey || '',
      lastFieldIdx: lastFieldIdx,
    }};
  }}

  function moveToFilterAction(targetKey, label) {{
    // Blur first; do not send Escape (reclaims focus on the prior widget).
    try {{
      if (doc.activeElement && doc.activeElement.blur) doc.activeElement.blur();
    }} catch (e) {{}}
    const focusBtn = function () {{
      focusAction(targetKey, label);
    }};
    focusBtn();
    setTimeout(focusBtn, 30);
    setTimeout(focusBtn, 80);
    setTimeout(focusBtn, 160);
    setTimeout(focusBtn, 280);
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
          return true;
        }}
        const any = focusable(root);
        if (any) {{ any.focus(); return true; }}
      }} catch (e) {{}}
    }}
    return false;
  }}

  function nodeInsideDataEditor(node, c) {{
    if (!c || !c.dataEditorKey || !node) return false;
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

  function advanceFrom(key, c) {{
    const idx = c.chain.indexOf(key);
    if (idx < 0) return;
    const r = rulesOf(c);
    if (r.enter_empty_product_to_below_last &&
        isProductKey(key) && !productHasSelection(key) && c.belowLast) {{
      focusKey(c.belowLast);
      return;
    }}
    if (idx >= c.chain.length - 1) {{
      if (c.dataEditorKey) {{
        focusDataEditor(c.dataEditorKey);
        return;
      }}
      if (c.addLineKey) clickKey(c.addLineKey);
      return;
    }}
    const nextKey = c.chain[idx + 1];
    if (c.aboveFirst && key === c.aboveFirst) {{
      closeOpenDatePickers();
      setTimeout(function () {{ focusKey(nextKey); }}, 60);
      return;
    }}
    focusKey(nextKey);
  }}

  function retreatFrom(key, c) {{
    const idx = c.chain.indexOf(key);
    if (idx <= 0) return;
    focusKey(c.chain[idx - 1]);
  }}

  function findColumn(key, c) {{
    const cols = c.columns || {{}};
    const names = gridRoles(c);
    for (let i = 0; i < names.length; i++) {{
      const name = names[i];
      const list = cols[name] || [];
      const idx = list.indexOf(key);
      if (idx >= 0) return {{ name: name, list: list, index: idx }};
    }}
    return null;
  }}

  function rowDeleteKey(widgetKey) {{
    const m = String(widgetKey || '').match(
      /^(.*)_r([^_]+)_(product|qty|rate|discount|qty_recv)$/
    );
    if (!m) return null;
    return m[1] + '_del_' + m[2];
  }}

  function rowProductKey(widgetKey) {{
    const m = String(widgetKey || '').match(
      /^(.*)_r([^_]+)_(product|qty|rate|discount)$/
    );
    if (!m) return null;
    return m[1] + '_r' + m[2] + '_product';
  }}

  function gridChain(c) {{
    const cols = c.columns || {{}};
    const roles = gridRoles(c);
    const lists = roles.map(function (name) {{ return cols[name] || []; }});
    const out = [];
    const n = Math.max.apply(null, lists.map(function (l) {{ return l.length; }}).concat([0]));
    for (let i = 0; i < n; i++) {{
      for (let r = 0; r < lists.length; r++) {{
        if (lists[r][i]) out.push(lists[r][i]);
      }}
    }}
    return out;
  }}

  function lastGridEdgeKey(c) {{
    const cols = c.columns || {{}};
    const roles = gridRoles(c);
    for (let i = 0; i < roles.length; i++) {{
      const list = cols[roles[i]] || [];
      if (list.length) return list[list.length - 1];
    }}
    return null;
  }}

  function advanceInGrid(key, c) {{
    const g = gridChain(c);
    const idx = g.indexOf(key);
    if (idx < 0 || idx >= g.length - 1) return;
    focusKey(g[idx + 1]);
  }}

  function retreatInGrid(key, c) {{
    const g = gridChain(c);
    const idx = g.indexOf(key);
    if (idx <= 0) return;
    focusKey(g[idx - 1]);
  }}

  function moveVertical(key, direction, c) {{
    const r = rulesOf(c);
    if (!r.arrows_up_down_same_column) return false;
    if (c.aboveFirst && key === c.aboveFirst) return false;

    if (c.belowLast && key === c.belowLast && direction < 0) {{
      const edge = lastGridEdgeKey(c);
      if (edge) focusKey(edge);
      return true;
    }}

    const hit = findColumn(key, c);
    if (!hit) return false;
    const next = hit.index + direction;
    if (next < 0) {{
      if (r.arrow_up_first_row_to_above_first && c.aboveFirst) {{
        focusKey(c.aboveFirst);
        return true;
      }}
      return true;
    }}
    if (next >= hit.list.length) {{
      if (r.arrow_down_last_row_to_below_last && c.belowLast) {{
        focusKey(c.belowLast);
        return true;
      }}
      return true;
    }}
    focusKey(hit.list[next]);
    return true;
  }}

  function isFilterRadioTarget(el) {{
    if (!el) return false;
    const t = (el.tagName || '').toLowerCase();
    const inputType = (el.type && String(el.type).toLowerCase()) || '';
    if (t === 'input' && inputType === 'radio') return true;
    if (el.getAttribute && el.getAttribute('role') === 'radio') return true;
    let n = el;
    while (n && n !== doc.body) {{
      if (n.getAttribute && n.getAttribute('data-testid') === 'stRadio') return true;
      if (n.getAttribute && n.getAttribute('role') === 'radiogroup') return true;
      n = n.parentElement;
    }}
    return false;
  }}

  function selectFilterRadioOption(el) {{
    if (!el) return;
    try {{
      const t = (el.tagName || '').toLowerCase();
      const inputType = (el.type && String(el.type).toLowerCase()) || '';
      if (t === 'input' && inputType === 'radio') {{
        el.checked = true;
        el.click();
        return;
      }}
      const roleRadio = el.closest ? el.closest('[role="radio"]') : null;
      if (roleRadio) {{ roleRadio.click(); return; }}
      const label = el.closest ? el.closest('label') : null;
      if (label) {{
        const input = label.querySelector('input[type="radio"]');
        if (input) {{ input.checked = true; input.click(); return; }}
        label.click();
      }}
    }} catch (e) {{}}
  }}

  function onKeyDown(ev) {{
    const isEnter = ev.key === 'Enter';
    const isRight = ev.key === 'ArrowRight';
    const isLeft = ev.key === 'ArrowLeft';
    const isUp = ev.key === 'ArrowUp';
    const isDown = ev.key === 'ArrowDown';
    const isTab = ev.key === 'Tab';
    const isDelete = ev.key === 'Delete';

    const key = activeKey();
    const c = resolveActiveCfg(key);
    const r = rulesOf(c);
    const linear = c.mode === 'linear_apply' || r.mode === 'linear_apply';
    const onRadio = isFilterRadioTarget(ev.target)
      || isFilterRadioTarget(doc.activeElement);

    // Payable-balance radio: Left/Right handled by filters chain nav.
    // Do not steal those keys here (would jump back to Alternate phone).
    if (linear && onRadio && (isLeft || isRight)) {{
      return;
    }}
    if (linear && onRadio && isEnter
        && !(ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) {{
      // Chain nav owns Enter→select; skip Apply click.
      return;
    }}
    if (linear && onRadio && isDown
        && !(ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) {{
      const pairRadio = linearButtonPair(c, r);
      if (pairRadio.applyKey) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        setTimeout(function () {{
          moveToFilterAction(pairRadio.applyKey, 'Apply');
        }}, 0);
        return;
      }}
    }}
    if (linear && onRadio && isUp
        && !(ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) {{
      // Fall through to linear retreat (previous field / Alternate phone).
    }}

    // From last non-radio filter field, Down → Apply, Left → Clear all.
    if (linear && key && (isDown || isLeft) && !onRadio &&
        !(ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) {{
      const pairEarly = linearButtonPair(c, r);
      const onLast = !!(
        pairEarly.lastFieldKey && key === pairEarly.lastFieldKey
      );
      if (onLast && pairEarly.applyKey && pairEarly.clearKey) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        const target = isDown ? pairEarly.applyKey : pairEarly.clearKey;
        const label = isDown ? 'Apply' : 'Clear all';
        setTimeout(function () {{ moveToFilterAction(target, label); }}, 0);
        return;
      }}
    }}

    if (linear) {{
      if (!isEnter && !isRight && !isLeft && !isUp && !isDown && !isTab) return;
      if ((isEnter || isRight || isLeft || isUp || isDown) &&
          (ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey)) return;
      if (isTab && (ev.ctrlKey || ev.metaKey || ev.altKey)) return;
    }} else {{
      if (!isEnter && !isRight && !isLeft && !isUp && !isDown && !isDelete && !isTab) return;
      if (ev.ctrlKey || ev.metaKey || ev.altKey || (ev.shiftKey && !isTab)) return;
    }}

    const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toLowerCase() : '';
    if (tag === 'textarea') return;

    // Open select lists normally keep arrows — except leaving the last filter
    // field for Clear / Apply (handled above).
    const pairPeek = linear ? linearButtonPair(c, r) : null;
    const onLastFieldPeek = !!(
      pairPeek
      && key
      && pairPeek.lastFieldKey
      && key === pairPeek.lastFieldKey
    );
    const exitLastField = !!(
      onLastFieldPeek && pairPeek.clearKey && pairPeek.applyKey
      && (isDown || isLeft)
    );
    if (listOpen(ev.target) && !exitLastField) return;

    if (!linear && (nodeInsideDataEditor(ev.target, c) ||
        nodeInsideDataEditor(doc.activeElement, c))) {{
      if (!isEnter) return;
      setTimeout(function () {{
        if (listOpen(doc.activeElement)) return;
        sendTab(doc.activeElement);
      }}, 10);
      return;
    }}

    if (!key) return;

    const inChain = c.chain.indexOf(key) >= 0;
    const onBelowLast = !!(c.belowLast && key === c.belowLast);
    const inGrid = !!findColumn(key, c);
    const onAboveFirst = !!(c.aboveFirst && key === c.aboveFirst);

    if (!linear && onAboveFirst && isTab) {{
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.shiftKey) {{
        setTimeout(function () {{ retreatFrom(key, c); }}, 0);
      }}
      return;
    }}
    if (!linear && onAboveFirst && r.above_first_is_date &&
        (isUp || isDown || isLeft || isRight)) {{
      return;
    }}

    if (!linear && isDelete) {{
      if (!r.delete_removes_line) return;
      if (!inGrid) return;
      const productKey = rowProductKey(key);
      if (!productKey || !productHasSelection(productKey)) return;
      const delKey = rowDeleteKey(key);
      if (!delKey) return;
      ev.preventDefault();
      ev.stopPropagation();
      setTimeout(function () {{ clickKey(delKey); }}, 0);
      return;
    }}

    if (linear) {{
      if (!inChain) return;
      const pair = linearButtonPair(c, r);
      const applyKey = pair.applyKey;
      const clearKey = pair.clearKey;
      const lastFieldIdx = pair.lastFieldIdx;
      const onClear = !!(clearKey && key === clearKey);
      const onApply = !!(applyKey && key === applyKey);
      const onLastField = !!(pair.lastFieldKey && key === pair.lastFieldKey);

      if (isEnter) {{
        const t = (ev.target && ev.target.tagName)
          ? ev.target.tagName.toLowerCase() : '';
        const inputType = (ev.target && ev.target.type)
          ? String(ev.target.type).toLowerCase() : '';
        if (inputType === 'radio' || onRadio) {{
          ev.preventDefault();
          ev.stopPropagation();
          selectFilterRadioOption(doc.activeElement || ev.target);
          return;
        }}
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
          if (applyKey) clickKey(applyKey);
        }}, 0);
        return;
      }}

      // Radio: Left/Right change options; Down/Up handled above / via chain.
      if (onRadio && (isLeft || isRight)) {{
        return;
      }}
      if (onRadio && isDown && applyKey) {{
        ev.preventDefault();
        ev.stopPropagation();
        setTimeout(function () {{ moveToFilterAction(applyKey, 'Apply'); }}, 0);
        return;
      }}

      // Never retreat "back" from the last non-radio filter field on Left/Down.
      if (onLastField && !onRadio && (isDown || isLeft)) {{
        ev.preventDefault();
        ev.stopPropagation();
        try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
        if (clearKey && applyKey) {{
          const target = isDown ? applyKey : clearKey;
          const label = isDown ? 'Apply' : 'Clear all';
          setTimeout(function () {{ moveToFilterAction(target, label); }}, 0);
        }}
        return;
      }}

      // Left/Right move between Clear and Apply; Up returns to last field.
      if (clearKey && applyKey) {{
        if ((onClear || onApply) && (isLeft || isRight || isUp || isDown)) {{
          ev.preventDefault();
          ev.stopPropagation();
          try {{ ev.stopImmediatePropagation(); }} catch (e) {{}}
          let target = '';
          let label = '';
          if (isUp && pair.lastFieldKey) {{
            target = pair.lastFieldKey;
          }} else if (isLeft && onApply) {{
            target = clearKey;
            label = 'Clear all';
          }} else if (isRight && onClear) {{
            target = applyKey;
            label = 'Apply';
          }} else if (isDown && onClear) {{
            target = applyKey;
            label = 'Apply';
          }}
          if (target) {{
            setTimeout(function () {{ focusAction(target, label); }}, 0);
          }}
          return;
        }}
      }}

      const forward = isDown || isRight || (isTab && !ev.shiftKey);
      const backward = isUp || isLeft || (isTab && ev.shiftKey);
      if (!forward && !backward) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (forward) {{
        setTimeout(function () {{ advanceFrom(key, c); }}, 0);
      }} else {{
        setTimeout(function () {{ retreatFrom(key, c); }}, 0);
      }}
      return;
    }}

    if (isUp || isDown) {{
      if (!inGrid && !onBelowLast) return;
      const handled = moveVertical(key, isDown ? 1 : -1, c);
      if (handled) {{
        ev.preventDefault();
        ev.stopPropagation();
      }}
      return;
    }}

    if (isLeft || isRight) {{
      if (inGrid && r.arrows_left_right_grid_only) {{
        ev.preventDefault();
        ev.stopPropagation();
        if (isLeft) {{
          setTimeout(function () {{ retreatInGrid(key, c); }}, 0);
        }} else {{
          setTimeout(function () {{ advanceInGrid(key, c); }}, 0);
        }}
        return;
      }}
      if (inGrid && !r.arrows_left_right_grid_only) {{
        return;
      }}
      if (r.save_cancel_horizontal && (isActionButtonKey(key) || onBelowLast)) {{
        const idx = c.chain.indexOf(key);
        if (idx < 0) return;
        const nextIdx = isRight ? idx + 1 : idx - 1;
        if (nextIdx < 0 || nextIdx >= c.chain.length) return;
        const target = c.chain[nextIdx];
        if (!(isActionButtonKey(target) || target === c.belowLast)) return;
        ev.preventDefault();
        ev.stopPropagation();
        setTimeout(function () {{ focusKey(target); }}, 0);
      }}
      return;
    }}

    if (isEnter) {{
      if (!inChain) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (r.enter_on_action_button_clicks && (isActionButtonKey(key) || onBelowLast)) {{
        setTimeout(function () {{ clickKey(key); }}, 0);
        return;
      }}
      setTimeout(function () {{ advanceFrom(key, c); }}, 0);
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

  function resolveFocusKey(node) {{
    let cur = node;
    while (cur && cur !== doc.body) {{
      const k = classKey(cur);
      if (k) return k;
      cur = cur.parentElement;
    }}
    return null;
  }}

  function onFocusIn(ev) {{
    const focused = resolveFocusKey(ev.target);
    const c = resolveActiveCfg(focused);
    if (!c.aboveFirst) return;
    if (nodeInDateCalendar(ev.target)) {{
      win.__vayFocusMgrPrevKey = c.aboveFirst;
      return;
    }}
    const nextKey = focused;
    const prev = win.__vayFocusMgrPrevKey;
    win.__vayFocusMgrPrevKey = nextKey || prev;
    if (prev && prev === c.aboveFirst && nextKey && nextKey !== c.aboveFirst) {{
      closeOpenDatePickers();
    }}
  }}

  function onFocusOut(ev) {{
    const leavingKey = resolveFocusKey(ev.target);
    const c = resolveActiveCfg(leavingKey);
    if (!c.aboveFirst) return;
    let node = ev.target;
    let leavingExpected = false;
    while (node && node !== doc.body) {{
      if (classKey(node) === c.aboveFirst) {{
        leavingExpected = true;
        break;
      }}
      node = node.parentElement;
    }}
    if (!leavingExpected) return;
    const related = ev.relatedTarget;
    if (nodeInDateCalendar(related)) return;
    setTimeout(function () {{
      const active = doc.activeElement;
      if (nodeInDateCalendar(active)) return;
      const still = activeKey();
      if (still === c.aboveFirst) return;
      closeOpenDatePickers();
    }}, 0);
  }}

  if (!win.__vayFocusMgrFocusIn) {{
    win.__vayFocusMgrFocusIn = onFocusIn;
    win.__vayFocusMgrFocusOut = onFocusOut;
    doc.addEventListener('focusin', onFocusIn, true);
    doc.addEventListener('focusout', onFocusOut, true);
  }} else {{
    try {{
      doc.removeEventListener('focusin', win.__vayFocusMgrFocusIn, true);
      doc.removeEventListener('focusout', win.__vayFocusMgrFocusOut, true);
    }} catch (e) {{}}
    win.__vayFocusMgrFocusIn = onFocusIn;
    win.__vayFocusMgrFocusOut = onFocusOut;
    doc.addEventListener('focusin', onFocusIn, true);
    doc.addEventListener('focusout', onFocusOut, true);
  }}

  function tryFocus() {{
    const c = win.__vayFocusMgrById[cfg.managerId] || cfg;
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
    focus_to = payload["focusTo"]
    component_key = config.component_key
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
