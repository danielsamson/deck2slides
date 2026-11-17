// Audit a rendered deck against a column grid and a unit grid (a guide, not a hard rule).
// Usage: node gridcheck.cjs <deck.html: sections 1920x1080> [margin=84 col=124 gutter=24 unit=12] ; prints per-slide misses and the share on grid.
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const [file, ...kv] = process.argv.slice(2); const o = { margin: 84, col: 124, gutter: 24, unit: 12 }; kv.forEach(a => { const [k, v] = a.split('='); o[k] = +v; });
  const b = await chromium.launch(process.env.D2S_CHROMIUM ? { executablePath: process.env.D2S_CHROMIUM } : {}); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.resolve(file)); await p.waitForTimeout(800);
  const res = await p.evaluate(o => {
    const pitch = o.col + o.gutter, starts = [], ends = [], spans = [];
    for (let i = 0; i < 12; i++) { starts.push(o.margin + i * pitch); ends.push(o.margin + i * pitch + o.col); for (let k = 1; k <= 12; k++) spans.push(k * pitch - o.gutter); }
    const near = (v, arr) => arr.some(a => Math.abs(a - v) <= 1), unit = v => Math.abs(v - Math.round(v / o.unit) * o.unit) <= 1;
    const out = []; let total = 0, good = 0;
    document.querySelectorAll('section').forEach(s => {
      const sr = s.getBoundingClientRect(), miss = [];
      const check = (e, tier) => {
        const r = e.getBoundingClientRect(); const x = Math.round(r.left - sr.left), y = Math.round(r.top - sr.top), w = Math.round(r.width), h = Math.round(r.height);
        if (w < 2 || h < 2 || (w >= 1900 && h >= 1000)) return; const text = /^(P|H1|H2|H3|SPAN)$/.test(e.tagName), thin = w < 12 || h < 12;
        const okx = near(x, starts) || unit(x) || x === 0, okw = near(w, spans) || unit(w) || thin || text && (w > 0), oky = unit(y) || thin, okh = thin || text || unit(h) || e.tagName === 'IMG' && unit(h);
        const rightEdge = x + w, okr = near(rightEdge, ends) || near(rightEdge, [1920 - o.margin, 1920]) || unit(rightEdge) || thin;
        total += 4; const bad = []; if (!okx) bad.push('x=' + x); if (!oky) bad.push('y=' + y); if (!okw) bad.push('w=' + w); if (!okh) bad.push('h=' + h); good += 4 - bad.length;
        if (bad.length) miss.push((e.className || e.tagName).toString().slice(0, 24) + ' ' + bad.join(' '));
      };
      [...s.children].filter(e => !['ASIDE'].includes(e.tagName)).forEach(e => { check(e, 1); if (/(^|\s)row(\s|$)/.test(e.className || '') && e.style.position === 'absolute') [...e.children].forEach(c => check(c, 2)); });
      out.push({ id: s.id, miss });
    });
    return { out, total, good };
  }, o);
  let n = 0; res.out.forEach(s => { if (s.miss.length) { n += s.miss.length; console.log(s.id.padEnd(12), s.miss.join(' | ')); } });
  console.log('on grid: ' + (100 * res.good / res.total).toFixed(1) + '% of ' + res.total + ' measurements, ' + n + ' elements with a miss');
  await b.close();
})();
