const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const ROOT = process.argv[2], OUTDIR = process.argv[3], BLOB = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), CONC = +(process.argv[5] || 4), ONLY = process.argv[6] ? process.argv[6].split(',') : null;
const FONTS = '/home/user/deck2slides/test-decks/the-drop-deck/toast/project/fonts/';
const MIME = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.gif': 'image/gif', '.webp': 'image/webp' };
const deck = JSON.parse(fs.readFileSync(path.join(ROOT, 'project/deck.json'), 'utf8')); fs.mkdirSync(OUTDIR, { recursive: true });
const ids = deck.order.map((id, i) => [i + 1, id]).filter(([n, id]) => !ONLY || ONLY.includes(id));
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] }); let next = 0; const fails = [];
  async function one(n, sid) {
    const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 }); const p = await ctx.newPage();
    await ctx.route('**/*', async route => {
      const u = new URL(route.request().url()); const f = (x, extra) => route.fulfill({ status: 200, contentType: MIME[path.extname(x).toLowerCase()] || 'application/octet-stream', body: fs.readFileSync(x) });
      try {
        if (u.host === 'viewer.test') {
          let pn = decodeURIComponent(u.pathname); if (pn === '/') pn = '/index.html';
          if (pn === '/project/deck.json') { const d = JSON.parse(JSON.stringify(deck)); d.order = [sid]; d.cover = sid; d.sections = {}; d.designSystems = []; return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(d) }); }
          let m = /^\/_blob\/([0-9a-f]+)/.exec(pn); if (m && BLOB[m[1]]) { if (process.env.NOIMG && !/\.woff2?$/.test(BLOB[m[1]])) return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64') }); return f(BLOB[m[1]]); }
          m = /^\/_fonts\/(.+)$/.exec(pn); if (m) return f(FONTS + m[1]);
          const fp = path.join(ROOT, pn); if (fs.existsSync(fp) && fs.statSync(fp).isFile()) return f(fp);
          return route.fulfill({ status: 404, body: '' });
        }
        if (u.host === 'fonts.googleapis.com') return route.fulfill({ status: 200, contentType: 'text/css', body: [400, 500, 700, 800].map(w => `@font-face{font-family:'Inter';font-weight:${w};src:url(https://viewer.test/_fonts/Inter-${w}.woff2) format('woff2')}`).join('') });
        return route.abort();
      } catch (e) { return route.abort(); }
    });
    try {
      await p.goto('https://viewer.test/', { waitUntil: 'load' });
      await p.waitForFunction(() => document.documentElement.hasAttribute('data-thumb-ready'), null, { timeout: 30000 });
      await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
      await p.screenshot({ path: path.join(OUTDIR, 'v%d.png'.replace('%d', n)) });
    } catch (e) { fails.push(sid + ': ' + e.message.slice(0, 80)); }
    await ctx.close();
  }
  async function worker() { while (next < ids.length) { const [n, sid] = ids[next++]; await one(n, sid); } }
  await Promise.all(Array.from({ length: CONC }, worker)); await b.close(); console.log('rendered', ids.length - fails.length, 'of', ids.length); console.log(fails.join('\n'));
})();
