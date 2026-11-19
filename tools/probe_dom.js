const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const ROOT = process.argv[2], SID = process.argv[3], NEEDLE = process.argv[4];
const BLOB = JSON.parse(fs.readFileSync(process.argv[5], 'utf8')); const FONTS = '/home/user/deck2slides/test-decks/the-drop-deck/toast/project/fonts/';
const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.woff2': 'font/woff2' };
const deck = JSON.parse(fs.readFileSync(path.join(ROOT, 'project/deck.json'), 'utf8'));
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] }); const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } }); const p = await ctx.newPage();
  await ctx.route('**/*', async route => { const u = new URL(route.request().url()); const f = x => route.fulfill({ status: 200, contentType: MIME[path.extname(x)] || 'application/octet-stream', body: fs.readFileSync(x) });
    if (u.host === 'viewer.test') { let pn = decodeURIComponent(u.pathname); if (pn === '/') pn = '/index.html'; if (pn === '/project/deck.json') { const d = JSON.parse(JSON.stringify(deck)); d.order = [SID]; d.cover = SID; d.sections = {}; d.designSystems = []; return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(d) }); }
      let m = /^\/_blob\/([0-9a-f]+)/.exec(pn); if (m && BLOB[m[1]]) return f(BLOB[m[1]]); m = /^\/_fonts\/(.+)$/.exec(pn); if (m) return f(FONTS + m[1]); const fp = path.join(ROOT, pn); if (fs.existsSync(fp) && fs.statSync(fp).isFile()) return f(fp); return route.fulfill({ status: 404, body: '' }); }
    if (u.host === 'fonts.googleapis.com') return route.fulfill({ status: 200, contentType: 'text/css', body: [400, 500, 700, 800].map(w => `@font-face{font-family:'Inter';font-weight:${w};src:url(https://viewer.test/_fonts/Inter-${w}.woff2) format('woff2')}`).join('') });
    return route.abort(); });
  await p.goto('https://viewer.test/'); await p.waitForFunction(() => document.documentElement.hasAttribute('data-thumb-ready'), null, { timeout: 30000 }); await p.waitForTimeout(500);
  const r = await p.evaluate(n => { const out = []; for (const e of document.querySelectorAll('*')) { if (e.children.length === 0 && (e.textContent || '').includes(n)) { let x = e; const chain = []; for (let i = 0; i < 4 && x; i++, x = x.parentElement) { const cs = getComputedStyle(x), r = x.getBoundingClientRect(); chain.push({ tag: x.tagName, cls: x.className && x.className.toString().slice(0, 40), w: Math.round(r.width * 10) / 10, l: Math.round(r.left), t: Math.round(r.top), ff: cs.fontFamily.slice(0, 30), fs: cs.fontSize, ls: cs.letterSpacing, ws: cs.wordSpacing, tw: cs.textWrap, pad: cs.padding, style: (x.getAttribute('style') || '').slice(0, 90) }); } out.push(chain); break; } } return out; }, NEEDLE);
  console.log(JSON.stringify(r, null, 1)); await b.close();
})();
