"""Visible browser controls and ordinary input helpers, shared by all target implementations."""

HELPERS = r'''
  const W = innerWidth, H = innerHeight;
  const css = e => getComputedStyle(e);
  const up = n => n.assignedSlot || n.parentElement || (n.parentNode && n.parentNode.host) || null;
  const shown = e => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && e.checkVisibility({opacityProperty: true, visibilityProperty: true}); };
  const inSvg = e => { for (let p = up(e); p; p = up(p)) if (p instanceof SVGSVGElement) return true; return false; };
  const top = p => !p || p === document.body || p === document.documentElement;
  const visibleRect = e => {
    const r = e.getBoundingClientRect();
    let x0 = Math.max(r.left, 0), y0 = Math.max(r.top, 0), x1 = Math.min(r.right, W), y1 = Math.min(r.bottom, H);
    for (let cur = e; ;) {
      const position = css(cur).position;
      if (position === "fixed") break;
      let cb = up(cur);
      if (position === "absolute")
        while (!top(cb) && css(cb).position === "static" && css(cb).transform === "none") cb = up(cb);
      if (top(cb)) break;
      const s = css(cb);
      if (s.overflowX !== "visible" || s.overflowY !== "visible") {
        const q = cb.getBoundingClientRect();
        if (s.overflowX !== "visible") { x0 = Math.max(x0, q.left); x1 = Math.min(x1, q.right); }
        if (s.overflowY !== "visible") { y0 = Math.max(y0, q.top); y1 = Math.min(y1, q.bottom); }
      }
      cur = cb;
    }
    return x1 - x0 >= 1 && y1 - y0 >= 1 ? [x0, y0, x1 - x0, y1 - y0] : null;
  };
  const clip = (v, n) => (v || "").replace(/\s+/g, " ").trim().slice(0, n);
  const tip = e => clip(e.getAttribute && e.getAttribute("title"), 200);
  const hidden = n => { if (n.nodeType !== 1) return false; const s = css(n);
    return s.display === "none" || s.visibility === "hidden"; };
  // Rendered text of a composed subtree (shadow roots and slots followed, form fields and svg excluded).
  const ctext = (root, n) => {
    let out = "";
    const visit = node => {
      if (out.length > n) return;
      if (node.nodeType === 3) { out += node.nodeValue + " "; return; }
      if (node.nodeType === 11) { for (const c of node.childNodes) visit(c); return; }
      if (node.nodeType !== 1) return;
      if (node instanceof SVGElement || ["SCRIPT", "STYLE", "TEMPLATE", "INPUT", "SELECT", "TEXTAREA"].includes(node.tagName)) return;
      if (hidden(node)) return;
      if (node.tagName === "SLOT") { for (const a of node.assignedNodes({flatten: true})) visit(a); return; }
      if (node.shadowRoot) { for (const c of node.shadowRoot.childNodes) visit(c); return; }
      for (const c of node.childNodes) visit(c);
    };
    visit(root);
    return clip(out, n);
  };
  const ROLES = new Set(["button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "combobox", "textbox", "searchbox", "slider", "spinbutton", "treeitem", "listbox"]);
  const NATIVE = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"]);
  const FIELDS = new Set(["INPUT", "SELECT", "TEXTAREA"]);
  const elements = () => {
    const out = [];
    const walk = root => { for (const c of root.children) { out.push(c); if (c.shadowRoot) walk(c.shadowRoot); walk(c); } };
    walk(document);
    return out;
  };
  const native = e => NATIVE.has(e.tagName) || (e.isContentEditable && !(up(e) && up(e).isContentEditable)) ||
    ROLES.has(e.getAttribute("role") || "");
  const eligible = e => {
    if (e instanceof SVGElement) return false;
    if (e.tagName === "INPUT" && e.type === "hidden") return false;
    if (native(e)) return true;
    if (clip(e.getAttribute("title"), 1)) return true;
    const p = up(e);
    return css(e).cursor === "pointer" && !(p && p.nodeType === 1 && css(p).cursor === "pointer");
  };
  const inside = (a, b, slack) => a.left >= b.left - slack && a.top >= b.top - slack && a.right <= b.right + slack &&
    a.bottom <= b.bottom + slack;
  const hash = s => { let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h.toString(16).padStart(8, "0"); };
  const caption = (e, scope) => {
    // The nearest text before the field inside its container (after it for check boxes and radios).
    const toggle = e.type === "checkbox" || e.type === "radio";
    const text = n => n.nodeType === 3 ? n.nodeValue : (n.nodeType === 1 && !hidden(n) && !FIELDS.has(n.tagName) &&
      !(n.querySelector && n.querySelector("input,select,textarea,button")) ? ctext(n, 80) : "");
    const walk = (start, back) => {
      for (let n = start; n; n = back ? n.previousSibling : n.nextSibling) {
        if (n.nodeType === 1 && (FIELDS.has(n.tagName) || n.tagName === "BUTTON" || n.tagName === "BR" ||
            (n.querySelector && n.querySelector("input,select,textarea,button")))) return "";
        const t = clip(text(n), 80); if (t) return t;
      }
      return ""; };
    let c = toggle ? walk(e.nextSibling, false) || walk(e.previousSibling, true) : walk(e.previousSibling, true);
    // Then the text before the field's enclosing elements (shadow hosts included), up to three levels.
    for (let p = up(e), i = 0; !c && p && p !== scope && p.nodeType === 1 && i < 3; p = up(p), i++)
      c = toggle ? walk(p.nextSibling, false) : walk(p.previousSibling, true);
    return c;
  };
  // Controls: elements merged into groups (an element wrapping exactly one eligible control is one control; a tooltip-
  // only container around several controls gives them its tooltip as context).
  const controls = limit => {
    const all = elements();
    const cands = all.filter(e => { try { return eligible(e) && shown(e) && !inSvg(e); } catch (x) { return false; } });
    const set = new Set(cands), parent = new Map(), kids = new Map();
    for (const e of cands) {
      let p = up(e); while (p && !set.has(p)) p = up(p);
      parent.set(e, p || null);
      if (p) { if (!kids.has(p)) kids.set(p, []); kids.get(p).push(e); }
    }
    const into = new Map();  // member -> group root
    const contextOf = new Map();
    const dropped = new Set();
    for (const e of cands) {
      const k = kids.get(e) || [];
      if (k.length === 1 && !kids.has(k[0]) && inside(k[0].getBoundingClientRect(), e.getBoundingClientRect(), 4)) {
        into.set(k[0], e);
      } else if (k.length >= 1 && !native(e) && css(e).cursor !== "pointer") {
        // A titled container around several controls is not a control itself; its tooltip names their context.
        dropped.add(e);
        if (tip(e)) for (const c of k) contextOf.set(c, tip(e).slice(0, 160));
      }
    }
    const root = e => { let r = e; while (into.has(r)) r = into.get(r); return r; };
    const groups = new Map();
    for (const e of cands) {
      if (dropped.has(e)) continue;
      const r = root(e); if (dropped.has(r)) continue;
      if (!groups.has(r)) groups.set(r, []); groups.get(r).push(e);
    }
    const out = [], counts = {};
    for (const [el, members] of groups) {
      if (out.length >= limit) return {out, truncated: true};
      const v = visibleRect(el); if (!v) continue;
      const field = members.find(m => FIELDS.has(m.tagName)) || null;
      const titled = [...members].reverse().find(m => tip(m));
      const c = {tag: el.tagName.toLowerCase()};
      const role = members.map(m => m.getAttribute("role")).find(Boolean); if (role) c.role = role;
      const button = members.find(m => m.tagName === "INPUT" && ["button", "submit", "reset"].includes(m.type));
      const text = button ? clip(button.value, 200) : ctext(el, 200); if (text) c.text = text;
      if (titled) c.title = tip(titled);
      const aria = members.map(m => m.getAttribute("aria-label")).find(Boolean); if (aria) c.aria = clip(aria, 200);
      if (field) {
        const labels = field.labels ? [...field.labels].map(l => ctext(l, 120)).filter(Boolean).join(" ") : "";
        const label = labels || caption(field, el.parentElement); if (label) c.label = clip(label, 120);
        if (field.tagName === "INPUT") c.type = field.type;
        if (field.name) c.name = clip(field.name, 80);
        if (field.placeholder) c.placeholder = clip(field.placeholder, 120);
        if (field.tagName === "SELECT") {
          c.value = field.value;
          c.options = [...field.options].slice(0, 60).map(o => ({label: clip(o.text, 60), value: clip(o.value, 60),
            selected: o.selected}));
        } else if (field.type === "checkbox" || field.type === "radio") { c.checked = field.checked; c.value = field.value; }
        else if (field.type === "file") c.file = true;
        else if (["button", "submit", "reset"].includes(field.type)) { delete c.value; }
        else if (field.type !== "password") { const raw = String(field.value || ""); c.value = raw.slice(0, 4000);
          if (raw.length > 4000) c.value_truncated = true; }
      } else if (el.isContentEditable) { c.value = (el.innerText || "").slice(0, 4000); }
      const ctx = members.map(m => contextOf.get(m)).find(Boolean);
      if (ctx) c.context = ctx;
      else if (!c.title && !c.aria && !c.label) {
        for (let p = up(el), i = 0; p && i < 5; p = up(p), i++) {
          const t = p.nodeType === 1 ? tip(p).slice(0, 160) : ""; if (t) { c.context = t; break; } }
      }
      if (members.some(m => m.disabled || m.hasAttribute("disabled") || m.getAttribute("aria-disabled") === "true")) c.disabled = true;
      if (members.some(m => m.hasAttribute("pressed") || m.getAttribute("aria-pressed") === "true")) c.pressed = true;
      const expanded = members.map(m => m.getAttribute("aria-expanded")).find(x => x !== null && x !== undefined);
      if (expanded) c.expanded = expanded === "true";
      const selected = members.map(m => m.getAttribute("aria-selected")).find(x => x !== null && x !== undefined);
      if (selected) c.selected = selected === "true";
      c.bounds = v.map(Math.round);
      const key = hash(JSON.stringify([c.tag, c.role, c.text, c.title, c.aria, c.label, c.context, c.type, c.name]));
      counts[key] = (counts[key] || 0) + 1;
      c.ref = "e" + key + (counts[key] > 1 ? "x" + counts[key] : "");
      c._el = el; c._field = field;
      out.push(c);
    }
    return {out, truncated: false};
  };
  // Drawing surfaces: visible top-level svg or canvas elements of at least 100x100 visible pixels.
  const surfaces = () => {
    const out = [];
    for (const e of elements()) {
      if (!(e instanceof SVGSVGElement || e instanceof HTMLCanvasElement)) continue;
      if (e instanceof SVGSVGElement && inSvg(e)) continue;
      if (!shown(e)) continue;
      const v = visibleRect(e);
      if (v && v[2] >= 100 && v[3] >= 100) out.push({el: e, v});
    }
    return out;
  };
'''

FIND_SCRIPT = r'''([spec, want]) => {''' + HELPERS + r'''
  if (spec.ref && spec.ref.startsWith("canvas")) { const s = surfaces()[Number(spec.ref.slice(6))]; return s ? s.el : null; }
  const list = controls(100000).out;
  let found;
  if (spec.ref) found = list.filter(c => c.ref === spec.ref);
  else {
    const exact = spec.exact !== false;
    const norm = v => (v || "").replace(/\s+/g, " ").trim();
    const same = (have, want) => exact ? norm(have) === norm(want) : norm(have).toLowerCase().includes(norm(want).toLowerCase());
    const implicit = c => c.role || ({a: "link", button: "button", select: "combobox", textarea: "textbox", summary: "button"}[c.tag]) ||
      (c.type === "checkbox" ? "checkbox" : c.type === "radio" ? "radio" : c.tag === "input" || c.type ? "textbox" : "button");
    const name = c => c.aria || c.label || c.text || c.title || "";
    if ("role" in spec) found = list.filter(c => implicit(c) === spec.role && (spec.name === undefined || same(name(c), spec.name)));
    else if ("label" in spec) found = list.filter(c => same(c.label, spec.label) || same(c.aria, spec.label));
    else if ("title" in spec) found = list.filter(c => same(c.title, spec.title));
    else if ("placeholder" in spec) found = list.filter(c => same(c.placeholder, spec.placeholder));
    else found = list.filter(c => same(c.text, spec.text));
  }
  const c = found[spec.nth || 0];
  if (!c && "text" in spec && !spec.ref) {
    // Fallback: the innermost visible element (outside drawings) whose rendered text matches, as on screen.
    const exact = spec.exact !== false;
    const norm = v => (v || "").replace(/\s+/g, " ").trim();
    const hits = elements().filter(e => { try { if (e instanceof SVGElement || inSvg(e) || !shown(e)) return false;
      const t = norm(ctext(e, 300)); return exact ? t === norm(spec.text) : t.toLowerCase().includes(norm(spec.text).toLowerCase());
    } catch (x) { return false; } });
    const within = (o, e) => { for (let p = up(o); p; p = up(p)) if (p === e) return true; return false; };
    const innermost = hits.filter(e => !hits.some(o => o !== e && within(o, e)));
    return innermost[spec.nth || 0] || null;
  }
  if (!c) return null;
  return want === "field" && c._field ? c._field : c._el;
}'''

BOX_SCRIPT = r'''(e) => {''' + HELPERS + r'''
  if (!e || !shown(e)) return null;
  const v = visibleRect(e);
  return v ? {x: v[0], y: v[1], width: v[2], height: v[3]} : null;
}'''

DROP_SCRIPT = r'''([x, y, name, type, data]) => {
  let el = document.elementFromPoint(x, y);
  while (el && el.shadowRoot) { const inner = el.shadowRoot.elementFromPoint(x, y); if (!inner || inner === el) break; el = inner; }
  if (!el) return {error: "nothing at the drop point"};
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  const transfer = new DataTransfer();
  transfer.items.add(new File([bytes], name, {type}));
  const fire = kind => el.dispatchEvent(new DragEvent(kind, {bubbles: true, cancelable: true, composed: true,
    clientX: x, clientY: y, dataTransfer: transfer}));
  fire("dragenter"); fire("dragover"); fire("drop");
  return {dropped: true};
}'''

SETTLE_SCRIPT = r'''([quiet, limit]) => new Promise(resolve => {
  const start = performance.now(); let last = start;
  const observer = new MutationObserver(() => { last = performance.now(); });
  const watch = root => { observer.observe(root, {subtree: true, childList: true, attributes: true, characterData: true});
    for (const e of root.querySelectorAll("*")) if (e.shadowRoot) watch(e.shadowRoot); };
  try { watch(document); } catch (x) {}
  const busy = () => { try { return document.getAnimations().some(a => a.playState === "running" &&
    a.effect && a.effect.getComputedTiming().iterations !== Infinity); } catch (x) { return false; } };
  const tick = () => {
    const now = performance.now();
    if ((now - last >= quiet && !busy()) || now - start >= limit) {
      observer.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))); return; }
    setTimeout(tick, 40);
  };
  setTimeout(tick, 40);
})'''

FETCH_SCRIPT = r'''async ([url, limit]) => {
  const response = await fetch(url);
  const blob = await response.blob();
  if (blob.size > limit) return {error: "too large", size: blob.size};
  const buffer = new Uint8Array(await blob.arrayBuffer());
  let binary = ""; for (let i = 0; i < buffer.length; i += 32768) binary += String.fromCharCode.apply(null, buffer.subarray(i, i + 32768));
  return {type: blob.type, size: blob.size, base64: btoa(binary)};
}'''

SNAPSHOT_SCRIPT = r"""([limits]) => {""" + HELPERS + r"""
  const result=controls(limits.controls);
  const controlsOut=result.out.map(c=>{const o={...c};delete o._el;delete o._field;return o;});
  const canvases=surfaces().map(({el,v},i)=>({ref:"canvas"+i,tag:el.tagName.toLowerCase(),bounds:v.map(Math.round)}));
  const text=(document.body ? document.body.innerText : "").slice(0,limits.text);
  return {title:document.title,viewport:[W,H],controls:controlsOut,controls_truncated:result.truncated,
          canvases,text,text_truncated:!!document.body&&document.body.innerText.length>limits.text};
}"""
