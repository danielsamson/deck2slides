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
  // A face is a Google Fonts link (href) or an uploaded file (src: project/... or /_blob/<id>, resolved like pictures).
  const fonts = Object.values(deck.faces || {}).map(f => {
    if (f.href) return '<link rel="stylesheet" href="' + f.href + '">';
    const fp = f.src && resolveImg(f.src.replace(/^project\//, ''), 'faces');
    if (!fp || !fs.existsSync(fp)) { console.log('UNMAPPED FONT', f.family, f.src); return ''; }
    // Sibling files of the same family by weight (GoogleSans-400 / GoogleSans-700) are registered too, so bold text is
    // measured with the real bold Google will draw, not the browser's synthetic bold (narrower: lines wrapped differently).
    const m0 = /^(.+?)-(\d{3})\.(woff2?|ttf|otf)$/i.exec(path.basename(fp)); const w0 = m0 ? +m0[2] : 400;
    const sibs = m0 ? fs.readdirSync(path.dirname(fp)).map(n => /^(.+?)-(\d{3})\.(woff2?|ttf|otf)$/i.exec(n)).filter(m => m && m[1] === m0[1] && +m[2] > w0).sort((a, b) => a[2] - b[2]) : [];
    const cuts = sibs.map(m => +m[2]); const faces = [[fp, 1, cuts.length ? cuts[0] - 1 : 1000]].concat(sibs.map((m, i) => [path.join(path.dirname(fp), m[0]), +m[2], i + 1 < cuts.length ? cuts[i + 1] - 1 : 1000]));
    return '<style>' + faces.map(([file, lo, hi]) => '@font-face{font-family:"' + f.family + '";src:url("file://' + file + '");font-weight:' + lo + ' ' + hi + '}').join('') + '</style>';
  }).join('');
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
  const b = await chromium.launch(process.env.D2S_CHROMIUM ? { executablePath: process.env.D2S_CHROMIUM } : {}); const p = await b.newPage({ viewport: { width: SLIDE_W, height: SLIDE_H }, deviceScaleFactor: 1 });
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
    const splitTop = str => { const out = []; let d = 0, cur = ''; for (const ch of str) { if (ch === '(') d++; if (ch === ')') d--; if (ch === ',' && d === 0) { out.push(cur.trim()); cur = ''; } else cur += ch; } if (cur.trim()) out.push(cur.trim()); return out; };
    const gradOf = (cs, g, warn) => {
      const bi = cs.backgroundImage; if (!bi || bi === 'none') return null;
      if (splitTop(bi).length > 1) { warn('several background layers: only dropped'); return null; }
      const m = /^(repeating-)?(linear|radial)-gradient\((.*)\)$/s.exec(bi.trim()); if (!m || m[1]) { warn('gradient type not supported'); return null; }
      const parts = splitTop(m[3]); let angle = 180, i = 0; const kind = m[2];
      if (kind === 'linear') {
        if (/deg$/.test(parts[0])) { angle = parseFloat(parts[0]); i = 1; }
        else if (/^to /.test(parts[0])) { const mp = { 'to top': 0, 'to right': 90, 'to bottom': 180, 'to left': 270, 'to top right': 45, 'to right top': 45, 'to bottom right': 135, 'to right bottom': 135, 'to bottom left': 225, 'to left bottom': 225, 'to top left': 315, 'to left top': 315 }; angle = mp[parts[0]] !== undefined ? mp[parts[0]] : 180; i = 1; }
      }
      let size = 'farthest-corner', at = [50, 50];
      if (kind === 'radial' && !/^rgba?\(/.test(parts[0])) {
        i = 1; const sm = /(closest-side|closest-corner|farthest-side|farthest-corner)/.exec(parts[0]); if (sm) size = sm[1];
        const am = /at\s+([\d.]+)%\s+([\d.]+)%/.exec(parts[0]); if (am) at = [parseFloat(am[1]), parseFloat(am[2])];
        else if (/at\s/.test(parts[0]) && !/at\s+center/.test(parts[0])) warn('radial-gradient position other than percentages: centred');
        if (/\d+px/.test(parts[0].replace(/at.*$/, ''))) warn('radial-gradient size in px: treated as farthest-corner');
      }
      const rad = angle * Math.PI / 180, len = kind === 'linear' ? Math.abs(g.w * Math.sin(rad)) + Math.abs(g.h * Math.cos(rad)) : Math.max(g.w, g.h) / 2;
      let stops = parts.slice(i).map(p => { const mm = /^(rgba?\([^)]*\))\s*(.*)$/.exec(p); if (!mm) return null; const c = col(mm[1]); let pos = null; if (mm[2]) { pos = parseFloat(mm[2]); if (mm[2].includes('px')) pos = pos / len * 100; } return { c, pos }; }).filter(Boolean);
      if (stops.length < 2) return null;
      if (stops[0].pos === null) stops[0].pos = 0; if (stops[stops.length - 1].pos === null) stops[stops.length - 1].pos = 100;
      for (let k = 1; k < stops.length - 1; k++) if (stops[k].pos === null) { let a = k - 1, b = k + 1; while (stops[b].pos === null) b++; stops[k].pos = stops[a].pos + (stops[b].pos - stops[a].pos) * (k - a) / (b - a); }
      return kind === 'radial' ? { kind, angle, stops, size, at } : { kind, angle, stops };
    };
    const clipOf = (cs, g, warn) => {
      const c = cs.clipPath; if (!c || c === 'none') return null;
      const dim = (v, L) => v.endsWith('%') ? parseFloat(v) / 100 : parseFloat(v) / L;
      let m = /^polygon\((.*)\)$/s.exec(c);
      if (m) { const ps = splitTop(m[1]); const st = /^(nonzero|evenodd)$/.test(ps[0]) ? 1 : 0; return { kind: 'poly', pts: ps.slice(st).map(q => { const [a, b] = q.trim().split(/\s+/); return [dim(a, g.w), dim(b, g.h)]; }) }; }
      m = /^(circle|ellipse)\((.*)\)$/s.exec(c);
      if (m) {
        const [spec, at] = m[2].split(/\s+at\s+/); const [px, py] = (at || '50% 50%').trim().split(/\s+/);
        const cx = dim(px, g.w), cy = dim(py || '50%', g.h); const sp = (spec || '').trim().split(/\s+/).filter(Boolean);
        if (m[1] === 'circle') { if (!sp.length || !/^[\d.]+(%|px)$/.test(sp[0])) { warn('circle() radius keyword not supported'); return null; } const r = sp[0].endsWith('%') ? parseFloat(sp[0]) / 100 * Math.sqrt((g.w * g.w + g.h * g.h) / 2) : parseFloat(sp[0]); return { kind: 'ellipse', cx, cy, rx: r / g.w, ry: r / g.h }; }
        if (sp.length < 2 || !/^[\d.]+(%|px)$/.test(sp[0])) { warn('ellipse() radius keyword not supported'); return null; }
        return { kind: 'ellipse', cx, cy, rx: dim(sp[0], g.w), ry: dim(sp[1], g.h) };
      }
      m = /^inset\((.*)\)$/s.exec(c);
      if (m) { const [ins, rnd] = m[1].split(/\s+round\s+/); const v = ins.trim().split(/\s+/); const t = v[0], r = v[1] || t, b = v[2] || t, l = v[3] || r;
        const T = dim(t, g.h), Rr = 1 - dim(r, g.w), Bb = 1 - dim(b, g.h), L = dim(l, g.w);
        if (rnd) warn('inset() with round drawn square'); return { kind: 'poly', pts: [[L, T], [Rr, T], [Rr, Bb], [L, Bb]] }; }
      warn('clip-path type not supported'); return null;
    };
    const ovOf = (el, sec, R, g) => {
      const out = []; let inheritR = 0;
      for (let a = el.parentElement; a && a !== sec; a = a.parentElement) {
        const c2 = getComputedStyle(a); if (!(/hidden|clip/.test(c2.overflowX) || /hidden|clip/.test(c2.overflowY))) continue;
        const b = a.getBoundingClientRect(), bl = parseFloat(c2.borderLeftWidth), bt = parseFloat(c2.borderTopWidth), br = parseFloat(c2.borderRightWidth), bb = parseFloat(c2.borderBottomWidth);
        const box = { x0: b.left - R.left + bl, y0: b.top - R.top + bt, x1: b.right - R.left - br, y1: b.bottom - R.top - bb };
        let r = c2.borderTopLeftRadius.includes('%') ? Math.min(b.width, b.height) * parseFloat(c2.borderTopLeftRadius) / 100 : parseFloat(c2.borderTopLeftRadius) || 0; box.r = Math.max(0, r - Math.max(bl, bt));
        const ex = g.cx - g.w / 2 < box.x0 - 0.5 || g.cy - g.h / 2 < box.y0 - 0.5 || g.cx + g.w / 2 > box.x1 + 0.5 || g.cy + g.h / 2 > box.y1 + 0.5;
        if (ex) out.push(box);
        else if (box.r > 0.5 && Math.abs(g.cx - g.w / 2 - box.x0) < 1 && Math.abs(g.cy - g.h / 2 - box.y0) < 1 && Math.abs(g.w - (box.x1 - box.x0)) < 1 && Math.abs(g.h - (box.y1 - box.y0)) < 1) inheritR = Math.max(inheritR, box.r);
      }
      return { out, inheritR };
    };
    let svgN = 0; const rasterId = { n: 0 };
    return [...document.querySelectorAll('section')].map((sec, si) => {
      const R = sec.getBoundingClientRect(); const warns = []; const rasterSkip = new Set(); const items = [{ type: 'shape', cx: 960, cy: 540, w: 1920, h: 1080, rot: 0, fill: col(getComputedStyle(sec).backgroundColor), grad: gradOf(getComputedStyle(sec), { w: 1920, h: 1080 }, () => {}), radius: 0, bg: 1 }];
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
            let word = k[0];
            if (flat && rg.getClientRects().length > 1) {   // one word on two lines: the browser broke it after a hyphen (close-|up); Slides would not
              const top0 = rg.getClientRects()[0].top, cr = document.createRange();
              for (let j = 1; j < word.length; j++) { cr.setStart(m, k.index + j); cr.setEnd(m, k.index + j + 1); const r2 = cr.getClientRects()[0];
                if (r2 && r2.top > top0 + r2.height * 0.5) { word = word.slice(0, j) + '\u000b' + word.slice(j); wraps++; lines++; risky = true; lastTop = r2.top; prevRight = rg.getClientRects()[rg.getClientRects().length - 1].right; break; } }
            }
            out += sep + word; cur += k[0].length + 1; pos = k.index + k[0].length;
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
        if (rasterSkip.has(el)) continue;
        const g = geom(el, R), op = opOf(el); if (!g.w && !g.h) continue;
        { // elements Google cannot draw natively (blur, group opacity over overlapping children) are rendered alone to a transparent picture
          const blur = /blur\(/.test(cs.filter); let grp = false;
          if (!blur && +cs.opacity < 1 && el.children.length > 1) { const rs = [...el.querySelectorAll('*')].filter(d => { const c3 = getComputedStyle(d); const bg3 = col(c3.backgroundColor); return d.tagName === 'IMG' || (bg3 && bg3.a > 0); }).map(d => d.getBoundingClientRect()); for (let a = 0; a < rs.length && !grp; a++) for (let b2 = a + 1; b2 < rs.length; b2++) if (Math.min(rs[a].right, rs[b2].right) - Math.max(rs[a].left, rs[b2].left) > 1 && Math.min(rs[a].bottom, rs[b2].bottom) - Math.max(rs[a].top, rs[b2].top) > 1) { grp = true; break; } }
          const glass = cs.backdropFilter && cs.backdropFilter !== 'none';
          if (glass && !blur && !grp) {
            // backdrop-filter (frosted glass): Slides has no backdrop blur. The panel's own box is captured as the browser paints it,
            // backdrop blur, tint, border and inset light included; its children stay native on top. Rounded mask and shadow are native.
            const rid = 'g_' + (rasterId.n++); el.setAttribute('data-gs-glass', rid); const b = el.getBoundingClientRect();
            const rv2 = parseFloat(cs.borderTopLeftRadius) || 0; const gr = Math.min(cs.borderTopLeftRadius.includes('%') ? Math.min(g.w, g.h) * rv2 / 100 : rv2, Math.min(g.w, g.h) / 2);
            items.push({ type: 'img', src: 'GLASS:' + rid, nw: b.width, nh: b.height, fit: 'fill', radius: gr, shadow: shadow(cs), op, pad: null, bw: null, cpath: null, ovclip: null, ...g, page: { x: b.left + window.scrollX, y: b.top + window.scrollY, w: b.width, h: b.height } });
            warns.push(el.tagName.toLowerCase() + ': backdrop-filter (' + cs.backdropFilter.split('(')[0] + ') drawn as a picture of the panel with its backdrop; text stays editable');
            if (!textOwner.has(el)) continue;
            el.__gsGlassed = true;      // its own text still becomes a text box (no fill, border or shadow: the picture has those)
          }
          if (blur || grp) {
            const all = [el, ...el.querySelectorAll('*')]; for (const d of all) if (d !== el) rasterSkip.add(d);
            let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const d of all) { const r = d.getBoundingClientRect(); if (!r.width && !r.height) continue; x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); }
            const sg = blur ? parseFloat(/blur\(([\d.]+)px/.exec(cs.filter)[1]) : 0, m = Math.ceil(sg * 3);
            x0 -= m; y0 -= m; x1 += m; y1 += m; const rid = 'r_' + (rasterId.n++); el.setAttribute('data-gs-r', rid);
            warns.push(el.tagName.toLowerCase() + ': ' + (blur ? 'blur' : 'group opacity over overlapping children') + ' drawn as a picture' + (el.textContent.trim() ? ' (its text is part of the picture)' : ''));
            items.push({ type: 'img', src: 'RASTER:' + rid, nw: x1 - x0, nh: y1 - y0, fit: 'fill', radius: 0, shadow: null, op: 1, pad: null, bw: null, cx: (x0 + x1) / 2 - R.left, cy: (y0 + y1) / 2 - R.top, w: x1 - x0, h: y1 - y0, rot: 0, page: { x: x0 + window.scrollX, y: y0 + window.scrollY, w: x1 - x0, h: y1 - y0 } });
            continue;
          }
        }
        { const w = [];  if (cs.filter !== 'none' && !/blur\(/.test(cs.filter)) w.push('filter (' + cs.filter.split('(')[0] + ') dropped'); if (cs.mixBlendMode !== 'normal') w.push('mix-blend-mode dropped'); if (+cs.opacity < 1 && el.children.length > 1) w.push('group opacity is applied per child (overlaps look darker)');
          if (w.length) warns.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '') + ': ' + w.join(', ')); }
        const pad = { l: parseFloat(cs.paddingLeft), r: parseFloat(cs.paddingRight), t: parseFloat(cs.paddingTop), b: parseFloat(cs.paddingBottom) };
        const bw = { l: parseFloat(cs.borderLeftWidth), r: parseFloat(cs.borderRightWidth), t: parseFloat(cs.borderTopWidth), b: parseFloat(cs.borderBottomWidth) };
        const bst = { l: cs.borderLeftStyle, r: cs.borderRightStyle, t: cs.borderTopStyle, b: cs.borderBottomStyle };
        const bc = { l: col(cs.borderLeftColor), r: col(cs.borderRightColor), t: col(cs.borderTopColor), b: col(cs.borderBottomColor) };
        const vis = k => bw[k] > 0 && bst[k] !== 'none' && bc[k].a > 0;
        const uniform = vis('l') && vis('r') && vis('t') && vis('b') && bw.l === bw.r && bw.l === bw.t && bw.l === bw.b;
        const rpct = cs.borderTopLeftRadius.includes('%'); const rv = parseFloat(cs.borderTopLeftRadius) || 0; const ell = rpct && rv >= 50 && Math.abs(g.w - g.h) > 1;
        let radius = Math.min(rpct ? Math.min(g.w, g.h) * Math.min(rv, 50) / 100 : rv, Math.min(g.w, g.h) / 2);   // CSS clamps a radius to half the box
        const gwarn = m => warns.push(el.tagName.toLowerCase() + ': ' + m); const grad = gradOf(cs, g, gwarn), cpath = clipOf(cs, g, gwarn), ov = ovOf(el, sec, R, g);
        if (ov.inheritR > radius) radius = ov.inheritR;
        const ovclip = ov.out.length ? ov.out : null;
        const sh = shadow(cs);
        if (el.tagName === 'svg') { const id = 'svg_' + (svgN++); el.setAttribute('data-gs', id); items.push({ type: 'svg', id, color: cs.color, ...g, op, qi: [...document.querySelectorAll('svg')].indexOf(el), alt: el.getAttribute('aria-label') || '' }); continue; }
        if (el.tagName === 'IMG') {
          { const ibg = col(cs.backgroundColor); if (ibg && ibg.a > 0) items.push({ type: 'shape', ...g, op, radius, ell, fill: ibg, grad: null, stroke: null, shadow: null }); }
          items.push({ type: el.dataset.clip ? 'clip' : 'img', src: decodeURI(el.src.replace('file://', '')), clip: el.dataset.clip || null, nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, radius, shadow: sh, op, pad, bw, cpath, ovclip, alt: el.getAttribute('alt') || '', border: uniform && bw.l > 0 ? { c: col(cs.borderTopColor), w: bw.l } : null, ...g });
        } else {
          const bg = col(cs.backgroundColor); const hasText = textOwner.has(el);
          if ((bg && bg.a > 0) || grad || uniform || hasText) {
            const it = { type: 'shape', ...g, op, radius, ell, fill: bg && bg.a > 0 && !grad ? bg : null, grad, cpath, ovclip, stroke: uniform ? { c: bc.l, w: bw.l, dash: bst.l === 'dashed' ? 'dash' : bst.l === 'dotted' ? 'dot' : null, cmpd: bst.l === 'double' ? 'dbl' : null } : null, shadow: sh, pad, bw };
            if (hasText) { it.text = textOf(el, cs, g); if (el.dataset.role) it.role = el.dataset.role; }
            if (el.__gsGlassed) Object.assign(it, { fill: null, grad: null, stroke: null, shadow: null });
            items.push(it);
          }
        }
        if (el.__gsGlassed) { /* borders are in the glass picture */ }
        else if (!uniform && radius > 0.5) { for (const k of ['l', 'r', 't', 'b']) if (vis(k))   // rounded box: each side is a band that follows the corners (geomclip.band_poly)
          items.push({ type: 'shape', ...g, op, radius: 0, ell: false, fill: bc[k], grad: null, cpath: null, ovclip, stroke: null, shadow: null, band: { k, bw: { l: vis('l') ? bw.l : 0, r: vis('r') ? bw.r : 0, t: vis('t') ? bw.t : 0, b: vis('b') ? bw.b : 0 }, r: radius } }); }
        else if (!uniform) for (const k of ['l', 'r', 't', 'b']) if (vis(k)) {
          const hw = g.w / 2, hh = g.h / 2, o = bw[k] / 2;
          const seg = k === 'l' ? [-hw + o, -hh, -hw + o, hh] : k === 'r' ? [hw - o, -hh, hw - o, hh] : k === 't' ? [-hw, -hh + o, hw, -hh + o] : [-hw, hh - o, hw, hh - o];
          items.push({ type: 'line', x1: g.cx + seg[0], y1: g.cy + seg[1], x2: g.cx + seg[2], y2: g.cy + seg[3], c: bc[k], w: bw[k], dash: bst[k] === 'dashed' ? 'dash' : bst[k] === 'dotted' ? 'dot' : null, op });
        }
      }
      const links = [...sec.querySelectorAll('a[href]')].filter(a => !a.textContent.trim()).map(e => ({ type: 'link', href: e.href, ...geom(e.offsetWidth ? e : e.parentElement, R) }));
      const aside = sec.querySelector(':scope > aside');   // speaker notes: plain text, carried to the PPTX notes page
      return { i: si, id: sec.id, layout: sec.dataset.layout || null, warns, items: items.concat(links), notes: aside ? aside.textContent.trim() : '' };
    });
  });
  const hideSt = await p.addStyleTag({ content: 'img,svg{visibility:hidden !important}' });
  for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: path.join(OUT, 'noimg_' + String(i + 1).padStart(2, '0') + '.png') });
  await hideSt.evaluate(e => e.remove());
  // raster islands: render each tagged element (and its children) alone on a transparent page at 2x
  { const isl = []; for (const d of data) for (const it of d.items) if (typeof it.src === 'string' && it.src.startsWith('RASTER:')) isl.push(it);
    if (isl.length) {
      fs.mkdirSync(path.join(OUT, 'raster'), { recursive: true });
      const tags = await p.evaluate(() => [...document.querySelectorAll('*')].map((e, i) => e.hasAttribute('data-gs-r') ? [i, e.getAttribute('data-gs-r')] : null).filter(Boolean));
      const p3 = await b.newPage({ viewport: { width: SLIDE_W, height: SLIDE_H }, deviceScaleFactor: 2 });
      await p3.goto('file://' + path.join(OUT, 'preview.html')); await p3.waitForTimeout(2500); await p3.evaluate(() => document.fonts.ready);
      await p3.evaluate(tg => { const all = document.querySelectorAll('*'); for (const [i, rid] of tg) all[i].setAttribute('data-gs-id', rid); }, tags);
      await p3.addStyleTag({ content: 'html,body{background:transparent !important}body *{visibility:hidden !important}[data-gs-r],[data-gs-r] *{visibility:visible !important}*{animation:none !important}' });
      for (const it of isl) {
        const rid = it.src.slice(7); const f = path.join(OUT, 'raster', rid + '.png');
        await p3.evaluate(r => document.querySelector('[data-gs-id="' + r + '"]').setAttribute('data-gs-r', 'on'), rid);
        await p3.screenshot({ path: f, clip: { x: it.page.x, y: it.page.y, width: it.page.w, height: it.page.h }, fullPage: true, omitBackground: true });
        await p3.evaluate(r => document.querySelector('[data-gs-id="' + r + '"]').removeAttribute('data-gs-r'), rid);
        it.src = f; delete it.page; }
      await p3.close(); } }
  // Glass panels: the page as painted up to the panel (everything after it in the document and the panel's own children hidden),
  // clipped to the panel's box.
  const glassItems = []; for (const d of data) for (const it of d.items) if (typeof it.src === 'string' && it.src.startsWith('GLASS:')) glassItems.push(it);
  if (glassItems.length) {
    fs.mkdirSync(path.join(OUT, 'raster'), { recursive: true });
    for (const it of glassItems) {
      const rid = it.src.slice(6), f = path.join(OUT, 'raster', rid + '.png');
      await p.evaluate(r => { const el = document.querySelector('[data-gs-glass="' + r + '"]'); const sec = el.closest('section'); window.__gsHidden = [];
        window.__gsColor = [el, el.style.color, el.style.webkitTextFillColor]; el.style.setProperty('color', 'transparent', 'important'); el.style.setProperty('-webkit-text-fill-color', 'transparent', 'important');   // its own text stays native
        for (const e of sec.querySelectorAll('*')) if ((el.contains(e) && e !== el) || (!e.contains(el) && (el.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING))) { window.__gsHidden.push([e, e.style.visibility]); e.style.setProperty('visibility', 'hidden', 'important'); }
      }, rid);
      await p.screenshot({ path: f, clip: { x: it.page.x, y: it.page.y, width: it.page.w, height: it.page.h }, fullPage: true });
      await p.evaluate(() => { for (const [e, v] of window.__gsHidden) { e.style.removeProperty('visibility'); if (v) e.style.visibility = v; }
        const [el, c, f] = window.__gsColor; el.style.removeProperty('color'); el.style.removeProperty('-webkit-text-fill-color'); if (c) el.style.color = c; if (f) el.style.webkitTextFillColor = f; });
      it.src = f; delete it.page;
    }
  }
  // Inline SVG (icons, the branching-lives drawing) has no native equivalent in Slides: each becomes a small transparent picture.
  // The deck CSS goes in too: an SVG can lean on it (transform-origin / transform-box on classed groups); without it scaled groups drift to the corner.
  const p2 = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 3 });
  for (const d of data) for (const it of d.items) {
    if (it.type === 'svg') {
      const markup = await p.evaluate(id => document.querySelector('[data-gs="' + id + '"]').outerHTML, it.id);
      await p2.setContent('<style>' + css + '\n*{animation:none !important;transition:none !important}</style><body style="margin:0;background:transparent"><div id="w" style="display:inline-block;color:' + it.color + '">' + markup.replace(/style="[^"]*"/, 'style="display:block;width:' + it.w + 'px;height:' + it.h + 'px"') + '</div></body>');
      it.src = path.join(OUT, 'svg', it.id + '.png'); await (await p2.$('#w')).screenshot({ path: it.src, omitBackground: true });
    }
    if (it.type === 'clip') { const g = path.join(GIFS, it.clip + '.gif'); it.gif = GIFS && fs.existsSync(g) ? g : null; }
  }
  // Looping drawings: an inline <svg> with infinite CSS animations inside it (or on an ancestor) is recorded frame by frame for a
  // looping GIF (d2s/loops.py encodes it). GIF transparency is on/off only, so each frame is the slide as painted up to the
  // drawing (backgrounds and everything before it in the document); what comes after it stays hidden, it is drawn natively on top.
  // Durations are nudged so every loop closes in one period (e.g. 16 s, 6 s and 9 s -> 16, 5.33, 8); the change is reported.
  const svgItems = []; data.forEach((d, si) => d.items.forEach(it => { if (it.type === 'svg') svgItems.push([si, it]); }));
  if (svgItems.length && process.env.D2S_LOOPS !== '0') {
    const live = path.join(OUT, 'preview_live.html');
    fs.writeFileSync(live, fs.readFileSync(path.join(OUT, 'preview.html'), 'utf8').replace('\n*{animation:none !important}', ''));
    const p4 = await b.newPage({ viewport: { width: SLIDE_W, height: SLIDE_H }, deviceScaleFactor: 1 });
    await p4.goto('file://' + live); await p4.waitForTimeout(1500); await p4.evaluate(() => document.fonts.ready);
    const FPS = +(process.env.D2S_LOOP_FPS || 12), MAXP = +(process.env.D2S_LOOP_MAX_S || 18) * 1000;
    for (const [si, it] of svgItems) {
      const plan = await p4.evaluate(({ qi, si, MAXP }) => {
        const svg = document.querySelectorAll('svg')[qi]; const sec = document.querySelectorAll('section')[si]; if (!svg || !sec) return null;
        const all = document.getAnimations();
        const rel = a => { const t = a.effect && a.effect.target; return t && (svg.contains(t) || t.contains(svg)); };
        const loops = all.filter(a => rel(a) && a.effect.getTiming().iterations === Infinity);
        if (!loops.length) return null;
        const durs = loops.map(a => a.effect.getTiming().duration), maxD = Math.max(...durs);
        const gcd = (a, b) => b ? gcd(b, a % b) : a; const r = durs.map(d => Math.round(d / 100)); const lcm = r.reduce((a, b) => a * b / gcd(a, b)) * 100;
        let P = lcm, cost = 0;
        if (lcm > MAXP) { cost = Infinity; for (let c = maxD; c <= Math.max(maxD, MAXP); c += 100) { const k = Math.max(...durs.map(d => Math.abs(c / Math.max(1, Math.round(c / d)) / d - 1))); if (k < cost - 1e-9) { cost = k; P = c; } } }
        loops.forEach(a => { const t = a.effect.getTiming(); const nd = P / Math.max(1, Math.round(P / t.duration)); a.effect.updateTiming({ duration: nd, delay: t.delay * nd / t.duration }); a.pause(); a._d2s0 = a.currentTime; });
        window.__d2sLoops = loops;
        for (const a of all) if (!loops.includes(a)) { try { a.finish(); } catch (e) { a.cancel(); } }
        for (const e of sec.querySelectorAll('*')) if (!svg.contains(e) && !e.contains(svg) && (svg.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)) e.style.setProperty('visibility', 'hidden', 'important');
        window.scrollTo(0, sec.getBoundingClientRect().top + window.scrollY);
        return { P, change: +(cost * 100).toFixed(1), durs, newDurs: loops.map(a => a.effect.getTiming().duration) };
      }, { qi: it.qi, si, MAXP });
      if (!plan) continue;
      let x0 = Math.max(0, it.cx - it.w / 2), y0 = Math.max(0, it.cy - it.h / 2), x1 = Math.min(SLIDE_W, it.cx + it.w / 2), y1 = Math.min(SLIDE_H, it.cy + it.h / 2);
      // The slide's ground (everything painted before the drawing, text made transparent) is captured once as a full-slide
      // picture placed under the GIF: soft backgrounds stay smooth PNG (GIF bands and streaks them), and the GIF's own baked
      // background comes from the same render, so its edge does not show against Slides' own drawing of the glows.
      await p4.evaluate(({ qi, si }) => { const svg = document.querySelectorAll('svg')[qi]; const sec = document.querySelectorAll('section')[si];
        for (const e of sec.querySelectorAll('*')) if (!svg.contains(e)) { e.style.setProperty('color', 'transparent', 'important'); e.style.setProperty('-webkit-text-fill-color', 'transparent', 'important'); }
        svg.style.setProperty('visibility', 'hidden', 'important'); }, { qi: it.qi, si });
      const groundF = path.join(OUT, 'loops', it.id + '_ground.png'); fs.mkdirSync(path.dirname(groundF), { recursive: true });
      await p4.screenshot({ path: groundF, clip: { x: 0, y: 0, width: SLIDE_W, height: SLIDE_H } });
      await p4.evaluate(({ qi }) => { document.querySelectorAll('svg')[qi].style.removeProperty('visibility'); }, { qi: it.qi });
      it.ground = groundF;
      const n = Math.max(2, Math.round(plan.P / 1000 * FPS)), dir = path.join(OUT, 'loops', it.id); fs.mkdirSync(dir, { recursive: true });
      for (let f = 0; f < n; f++) {
        await p4.evaluate(t => window.__d2sLoops.forEach(a => { a.currentTime = a._d2s0 + t; }), f * plan.P / n);
        await p4.screenshot({ path: path.join(dir, 'f_' + String(f).padStart(5, '0') + '.png'), clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 } });
      }
      it.loop = { dir, fps: n / (plan.P / 1000), frames: n, period_ms: plan.P, durations_ms: plan.durs, adjusted_ms: plan.newDurs, max_change_pct: plan.change };
      Object.assign(it, { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0 });
      await p4.evaluate(() => location.reload()); await p4.waitForTimeout(1200); await p4.evaluate(() => document.fonts.ready);
    }
    await p4.close();
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
