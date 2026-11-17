// Reads a Slides-artifact deck (deck.json, deck.css, slides/*.html), lays every slide out in a headless browser and
// writes slides.json: for each slide, an ordered list of native pieces (shapes, pictures, lines, text) with exact
// geometry and type, plus fonts.json (families used and their natural line height as the browser measures it).
// Usage: node extract.cjs --src <deck dir> --out <dir> [--assets <map.json>] [--gifs <dir of clip gifs>]
//   --assets  optional JSON {"<blob id>": "<image path>"}; a path is relative to the map file. Without it, blob ids are
//             looked up as <src>/blobs/<id>.* , and plain relative paths, http(s) URLs and data: URIs work directly.
//   --gifs    folder of <clip name>.gif for <img data-video> elements (clip name = file name of the video's still)
// Needs NODE_PATH to contain playwright (e.g. NODE_PATH=$(npm root -g)).
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const A = {}; for (let i = 2; i < process.argv.length; i += 2) A[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const root = path.resolve(A.src), OUT = path.resolve(A.out), GIFS = A.gifs ? path.resolve(A.gifs) : '';
const AMAPF = A.assets || ''; const AMAP = AMAPF ? JSON.parse(fs.readFileSync(AMAPF, 'utf8')) : {}; const AMAPDIR = AMAPF ? path.dirname(path.resolve(AMAPF)) : '';
const ICONS = JSON.parse(fs.readFileSync(path.join(__dirname, 'icons.json'), 'utf8'));   // x-icon name -> svg markup
const SLIDE_W = 1920, SLIDE_H = 1080;
function resolveImg(src, id) {
  if (/^\/_blob\/([0-9a-f]+)/.test(src)) {
    const h = /^\/_blob\/([0-9a-f]+)/.exec(src)[1];
    if (AMAP[h]) return path.resolve(AMAPDIR, AMAP[h]);
    const dir = path.join(root, 'blobs'); if (fs.existsSync(dir)) { const f = fs.readdirSync(dir).find(n => n.startsWith(h)); if (f) return path.resolve(dir, f); }
    return null;
  }
  if (/^data:/.test(src)) { const m = /^data:([^;,]+)(;base64)?,(.*)$/s.exec(src); const ext = (m[1].split('/')[1] || 'png').replace('svg+xml', 'svg'); const p = path.join(OUT, 'dl', 'data_' + require('crypto').createHash('sha1').update(src).digest('hex').slice(0, 10) + '.' + ext); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, m[2] ? Buffer.from(m[3], 'base64') : decodeURIComponent(m[3])); return p; }
  if (/^https?:/.test(src)) return 'URL:' + src;
  return path.resolve(root, src);
}
async function download(url) { const p = path.join(OUT, 'dl', require('crypto').createHash('sha1').update(url).digest('hex').slice(0, 10) + path.extname(new URL(url).pathname)); if (!fs.existsSync(p)) { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(await (await fetch(url)).arrayBuffer())); } return p; }
(async () => {
  fs.mkdirSync(path.join(OUT, 'svg'), { recursive: true });
  const deck = JSON.parse(fs.readFileSync(path.join(root, 'deck.json'), 'utf8')); const css = fs.readFileSync(path.join(root, 'deck.css'), 'utf8');
  const fonts = Object.values(deck.faces).map(f => '<link rel="stylesheet" href="' + f.href + '">').join('');
  let html = '<!doctype html><meta charset="utf-8">' + fonts + '<style>*{margin:0}body{background:#444}section{position:relative;width:1920px;height:1080px;box-sizing:border-box;overflow:hidden;margin-bottom:20px}hr{border:0}img{display:block}aside{display:none}x-shape{display:block}x-shape[kind=ellipse]{border-radius:50%}x-icon{display:block}section>*{position:relative}' + css + '\n*{animation:none !important}</style>';
  for (const id of deck.order) {
    let s = fs.readFileSync(path.join(root, 'slides', id + '.html'), 'utf8');
    const imgs = [...s.matchAll(/<img([^>]*?)src="([^"]+)"([^>]*)>/g)]; const rep = new Map();
    for (const m of imgs) { let f = resolveImg(m[2], id); if (f && f.startsWith('URL:')) f = await download(f.slice(4)); rep.set(m[0], f); if (!f) console.log('UNMAPPED', id, m[2]); }
    s = s.replace(/<img([^>]*?)src="([^"]+)"([^>]*)>/g, (m, a, src, b) => { const f = rep.get(m); if (!f) return m;
      const clip = /data-video=/.test(m) ? ' data-clip="' + path.basename(f).replace(/\.\w+$/, '') + '"' : '';
      return '<img' + a + 'src="file://' + f + '"' + clip + b + '>'; });
    s = s.replace(/<x-icon name="([^"]+)"([^>]*)><\/x-icon>/g, (m, name, a) => ICONS[name] ? '<x-icon name="' + name + '"' + a + '>' + ICONS[name] + '</x-icon>' : (console.log('UNKNOWN ICON', id, name, '(add it to icons.json)'), m));
    html += s;
  }
  fs.writeFileSync(path.join(OUT, 'preview.html'), html);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: SLIDE_W, height: SLIDE_H }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.join(OUT, 'preview.html')); await p.waitForTimeout(2500); await p.evaluate(() => document.fonts.ready);
  const secs = await p.$$('section');
  for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: path.join(OUT, 'full_' + String(i + 1).padStart(2, '0') + '.png') });
  const data = await p.evaluate(() => {
    const col = c => { const m = /rgba?\(([^)]+)\)/.exec(c); if (!m) return null; const v = m[1].split(',').map(parseFloat); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
    const rotOf = e => { let a = 0; for (let x = e; x && x.tagName !== 'SECTION'; x = x.parentElement) { const t = getComputedStyle(x).transform; if (t && t !== 'none') { const m = new DOMMatrix(t); a += Math.atan2(m.b, m.a) * 180 / Math.PI; } } return a; };
    const opOf = e => { let o = 1; for (let x = e; x && x.tagName !== 'SECTION'; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o; };
    const geom = (e, R) => { const b = e.getBoundingClientRect(), w = e.offsetWidth === undefined ? b.width : e.offsetWidth, h = e.offsetHeight === undefined ? b.height : e.offsetHeight; return { cx: b.left + b.width / 2 - R.left, cy: b.top + b.height / 2 - R.top, w, h, rot: rotOf(e) }; };
    const shadow = cs => { const s = cs.boxShadow; if (!s || s === 'none') return null; const c = col(s); const n = s.replace(/rgba?\([^)]+\)/, '').trim().split(/\s+/).map(parseFloat); return { c, x: n[0], y: n[1], blur: n[2] }; };
    const fam = s => s.fontFamily.split(',')[0].replace(/['"]/g, '').trim();
    let svgN = 0;
    return [...document.querySelectorAll('section')].map((sec, si) => {
      const R = sec.getBoundingClientRect(); const warns = []; const items = [{ type: 'shape', cx: 960, cy: 540, w: 1920, h: 1080, rot: 0, fill: col(getComputedStyle(sec).backgroundColor), radius: 0, bg: 1 }];
      const textOwner = new Map();
      // Which element owns each run of text: the nearest non-inline ancestor.
      const tw = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT); let n;
      while ((n = tw.nextNode())) {
        if (!n.nodeValue.trim()) continue; let el = n.parentElement; if (el.closest('aside,svg,script,style')) continue;
        while (getComputedStyle(el).display.startsWith('inline') && el.parentElement !== sec) el = el.parentElement;
        textOwner.set(el, 1);
      }
      const textOf = (el, cs, g) => {
        const runs = []; let lastTop = null, lines = 1, maxChars = 0, cur = 0, prevRight = 0, maxRight = -1e9, wraps = 0, risky = false; const flat = Math.abs(g.rot) < 0.01;
        const eb = el.getBoundingClientRect(), cRight = eb.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth), cW = eb.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        const pt = parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth), pb = parseFloat(cs.paddingBottom) + parseFloat(cs.borderBottomWidth);
        const push = (t, pe) => { if (!t) return; const s = getComputedStyle(pe); if (s.textTransform === 'uppercase') t = t.toUpperCase();
          const base = { color: col(s.color), w: +s.fontWeight, fam: fam(s), fs: parseFloat(s.fontSize), it: s.fontStyle === 'italic', ul: s.textDecorationLine.includes('underline'), ls: s.letterSpacing === 'normal' ? 0 : parseFloat(s.letterSpacing) };
          const has = ch => ch.charCodeAt(0) < 0x2000 || ch === '\u000b' || /[\u2018\u2019\u201c\u201d\u2013\u2014\u2026\u20ac]/.test(ch) || (() => { const c = (window.__cv = window.__cv || document.createElement('canvas').getContext('2d')); const f = s.fontWeight + ' 40px "' + base.fam + '", '; c.font = f + 'monospace'; const a = c.measureText(ch).width; c.font = f + 'Times New Roman'; const b2 = c.measureText(ch).width; c.font = f + 'Impact, fantasy'; return a === b2 && a === c.measureText(ch).width; })();
          let buf = '', ok = true;
          for (const ch of t) { const h = has(ch); if (h !== ok && buf) { runs.push({ ...base, t: buf, fam: ok ? base.fam : 'Arial', w: ok ? base.w : (base.w >= 600 ? 700 : 400) }); buf = ''; } ok = h; buf += ch; }
          if (buf) runs.push({ ...base, t: buf, fam: ok ? base.fam : 'Arial', w: ok ? base.w : (base.w >= 600 ? 700 : 400) }); };
        const w2 = document.createTreeWalker(el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT); let m;
        while ((m = w2.nextNode())) {
          if (m.nodeType === 1) { if (m.tagName === 'BR') { runs.push({ br: 1 }); lastTop = null; lines++; maxChars = Math.max(maxChars, cur); cur = 0; } continue; }
          const txt = m.nodeValue; const re = /\S+/g; let k, out = '', pos = 0; const rg = document.createRange();
          while ((k = re.exec(txt))) {
            rg.setStart(m, k.index); rg.setEnd(m, k.index + k[0].length); const rc = rg.getClientRects()[0];
            let sep = /\s/.test(txt.slice(pos, k.index)) ? ' ' : '';
            if (rc && flat) { if (lastTop !== null && rc.top > lastTop + rc.height * 0.5) { if (cRight - (prevRight + parseFloat(cs.fontSize) * 0.28 + rc.width) > -0.03 * cW) risky = true; sep = '\u000b'; wraps++; lines++; maxChars = Math.max(maxChars, cur); cur = 0; } lastTop = rc.top; prevRight = rc.right; maxRight = Math.max(maxRight, rc.right); }
            out += sep + k[0]; cur += k[0].length + 1; pos = k.index + k[0].length;
          }
          if (/\s$/.test(txt) && out) out += ' ';
          push(out, m.parentElement);
        }
        maxChars = Math.max(maxChars, cur);
        const lhpx = cs.lineHeight === 'normal' ? parseFloat(cs.fontSize) * 1.2 : parseFloat(cs.lineHeight);
        if (!flat) lines = Math.max(lines, Math.round((g.h - pt - pb) / lhpx));
        const flex = cs.display.includes('flex');
        return { runs, lines, maxChars, risky, wraps, over: Math.max(0, maxRight - cRight), tight: flat && cRight - maxRight < 0.006 * cW + 1, fs: parseFloat(cs.fontSize), lh: cs.lineHeight === 'normal' ? null : parseFloat(cs.lineHeight) / parseFloat(cs.fontSize), fam: fam(cs),
          align: flex ? (cs.justifyContent === 'center' ? 'center' : 'left') : (cs.textAlign === 'center' ? 'center' : (cs.textAlign === 'right' || cs.textAlign === 'end') ? 'right' : 'left'),
          anchor: flex && cs.alignItems === 'center' ? 'middle' : 'top', nowrap: cs.whiteSpace === 'nowrap', link: (el.closest('a[href]') || {}).href || null };
      };
      const ew = document.createTreeWalker(sec, NodeFilter.SHOW_ELEMENT, { acceptNode: e => (e.tagName === 'ASIDE' || e.closest('svg') && e.tagName !== 'svg') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT }); let el;
      while ((el = ew.nextNode())) {
        const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
        const g = geom(el, R), op = opOf(el); if (!g.w && !g.h) continue;
        { const w = []; if (cs.backgroundImage && cs.backgroundImage !== 'none' && el.tagName !== 'IMG') w.push('background-image/gradient dropped'); if (cs.clipPath !== 'none') w.push('clip-path dropped'); if (cs.filter !== 'none') w.push('filter (' + cs.filter.split('(')[0] + ') dropped'); if (cs.mixBlendMode !== 'normal') w.push('mix-blend-mode dropped'); if (cs.overflow === 'hidden' && [...el.children].some(c => { const b = c.getBoundingClientRect(), e = el.getBoundingClientRect(); return b.width && (b.left < e.left - 0.5 || b.top < e.top - 0.5 || b.right > e.right + 0.5 || b.bottom > e.bottom + 0.5); })) w.push('overflow:hidden clips a child (clip not reproduced)'); if (+cs.opacity < 1 && el.children.length > 1) w.push('group opacity is applied per child (overlaps look darker)'); if (['l', 't'].some(k => ({ l: cs.borderLeftStyle, t: cs.borderTopStyle })[k] === 'double')) w.push('double border drawn as solid');
          if (w.length) warns.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '') + ': ' + w.join(', ')); }
        const pad = { l: parseFloat(cs.paddingLeft), r: parseFloat(cs.paddingRight), t: parseFloat(cs.paddingTop), b: parseFloat(cs.paddingBottom) };
        const bw = { l: parseFloat(cs.borderLeftWidth), r: parseFloat(cs.borderRightWidth), t: parseFloat(cs.borderTopWidth), b: parseFloat(cs.borderBottomWidth) };
        const bst = { l: cs.borderLeftStyle, r: cs.borderRightStyle, t: cs.borderTopStyle, b: cs.borderBottomStyle };
        const bc = { l: col(cs.borderLeftColor), r: col(cs.borderRightColor), t: col(cs.borderTopColor), b: col(cs.borderBottomColor) };
        const vis = k => bw[k] > 0 && bst[k] !== 'none' && bc[k].a > 0;
        const uniform = vis('l') && vis('r') && vis('t') && vis('b') && bw.l === bw.r && bw.l === bw.t && bw.l === bw.b;
        const rpct = cs.borderTopLeftRadius.includes('%'); const rv = parseFloat(cs.borderTopLeftRadius) || 0; const ell = rpct && rv >= 50 && Math.abs(g.w - g.h) > 1;
        let radius = rpct ? Math.min(g.w, g.h) * Math.min(rv, 50) / 100 : rv;
        const sh = shadow(cs);
        if (el.tagName === 'svg') { const id = 'svg_' + (svgN++); el.setAttribute('data-gs', id); items.push({ type: 'svg', id, color: cs.color, ...g, op }); continue; }
        if (el.tagName === 'IMG') {
          items.push({ type: el.dataset.clip ? 'clip' : 'img', src: decodeURI(el.src.replace('file://', '')), clip: el.dataset.clip || null, nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, radius, shadow: sh, op, pad, bw, ...g });
        } else {
          const bg = col(cs.backgroundColor); const hasText = textOwner.has(el);
          if ((bg && bg.a > 0) || uniform || hasText) {
            const it = { type: 'shape', ...g, op, radius, ell, fill: bg && bg.a > 0 ? bg : null, stroke: uniform ? { c: bc.l, w: bw.l, dash: bst.l === 'dashed' ? 'dash' : bst.l === 'dotted' ? 'dot' : null } : null, shadow: sh, pad, bw };
            if (hasText) it.text = textOf(el, cs, g);
            items.push(it);
          }
        }
        if (!uniform) for (const k of ['l', 'r', 't', 'b']) if (vis(k)) {
          const hw = g.w / 2, hh = g.h / 2, o = bw[k] / 2;
          const seg = k === 'l' ? [-hw + o, -hh, -hw + o, hh] : k === 'r' ? [hw - o, -hh, hw - o, hh] : k === 't' ? [-hw, -hh + o, hw, -hh + o] : [-hw, hh - o, hw, hh - o];
          items.push({ type: 'line', x1: g.cx + seg[0], y1: g.cy + seg[1], x2: g.cx + seg[2], y2: g.cy + seg[3], c: bc[k], w: bw[k], dash: bst[k] === 'dashed' ? 'dash' : bst[k] === 'dotted' ? 'dot' : null, op });
        }
      }
      const links = [...sec.querySelectorAll('a[href]')].filter(a => !a.textContent.trim()).map(e => ({ type: 'link', href: e.href, ...geom(e.offsetWidth ? e : e.parentElement, R) }));
      return { i: si, id: sec.id, warns, items: items.concat(links) };
    });
  });
  await p.addStyleTag({ content: 'img,svg{visibility:hidden !important}' });
  for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: path.join(OUT, 'noimg_' + String(i + 1).padStart(2, '0') + '.png') });
  // Inline SVG (icons, the branching-lives drawing) has no native equivalent in Slides: each becomes a small transparent picture.
  const p2 = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 3 });
  for (const d of data) for (const it of d.items) {
    if (it.type === 'svg') {
      const markup = await p.evaluate(id => document.querySelector('[data-gs="' + id + '"]').outerHTML, it.id);
      await p2.setContent('<body style="margin:0;background:transparent"><div id="w" style="display:inline-block;color:' + it.color + '">' + markup.replace(/style="[^"]*"/, 'style="display:block;width:' + it.w + 'px;height:' + it.h + 'px"') + '</div></body>');
      it.src = path.join(OUT, 'svg', it.id + '.png'); await (await p2.$('#w')).screenshot({ path: it.src, omitBackground: true });
    }
    if (it.type === 'clip') { const g = path.join(GIFS, it.clip + '.gif'); it.gif = GIFS && fs.existsSync(g) ? g : null; }
  }
  // Natural line height per family, as the browser measures it (line-height: normal). Cross-checked against the font file by fonts.py.
  const fontInfo = await p.evaluate(() => { const o = {}; const seen = new Set();
    for (const e of document.querySelectorAll('section *')) { const cs = getComputedStyle(e); if (!e.childNodes.length || ![...e.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim())) continue;
      const fam = cs.fontFamily.split(',')[0].replace(/['"]/g, '').trim(); (o[fam] = o[fam] || { weights: [] }); if (!o[fam].weights.includes(+cs.fontWeight)) o[fam].weights.push(+cs.fontWeight); }
    for (const fam of Object.keys(o)) { const d = document.createElement('span'); d.style.cssText = 'position:absolute;visibility:hidden;font:400 1000px/normal "' + fam + '", Arial;white-space:nowrap'; d.textContent = 'Hxg'; document.body.appendChild(d); o[fam].naturalBrowser = d.getBoundingClientRect().height / 1000; d.remove(); o[fam].weights.sort(); }
    return o; });
  fs.writeFileSync(path.join(OUT, 'fonts.json'), JSON.stringify(fontInfo, null, 1));
  fs.writeFileSync(path.join(OUT, 'slides.json'), JSON.stringify(data, null, 1));
  console.log(data.map(d => d.id + ':' + d.items.length).join(' '));
  await b.close();
})();
