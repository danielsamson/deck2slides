// Usage: node census.cjs <work dir containing preview.html> <out.json>
// Measures computed style of every visible element of a rendered deck (the deck's own classes kept), for design-system derivation.
const { chromium } = require('playwright'); const path = require('path'), fs = require('fs');
(async () => {
  const [work, out] = process.argv.slice(2);
  const b = await chromium.launch(process.env.D2S_CHROMIUM ? { executablePath: process.env.D2S_CHROMIUM } : {});
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.resolve(work, 'preview.html')); await p.waitForTimeout(2500);
  const rows = await p.evaluate(() => {
    const px = v => parseFloat(v) || 0, res = [];
    document.querySelectorAll('section').forEach((s, si) => {
      const sr = s.getBoundingClientRect();
      s.querySelectorAll('*').forEach(e => {
        const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return;
        const c = getComputedStyle(e), own = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
        res.push({ slide: s.id || si, tag: e.tagName.toLowerCase(), cls: e.className && e.className.baseVal === undefined ? e.className : '', inline: !!e.getAttribute('style'),
          x: Math.round(r.x - sr.x), y: Math.round(r.y - sr.y), w: Math.round(r.width), h: Math.round(r.height), text: own.slice(0, 60),
          font: c.fontFamily.split(',')[0].replace(/["']/g, ''), size: px(c.fontSize), weight: +c.fontWeight, ls: px(c.letterSpacing), lh: c.lineHeight === 'normal' ? 0 : +(px(c.lineHeight) / px(c.fontSize)).toFixed(2),
          color: c.color, bg: c.backgroundColor, radius: c.borderTopLeftRadius, shadow: c.boxShadow, border: c.borderTopWidth + ' ' + c.borderTopStyle + ' ' + c.borderTopColor,
          pad: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft].map(px), gap: px(c.columnGap) || px(c.rowGap), pos: c.position });
      });
    });
    return res;
  });
  fs.writeFileSync(out, JSON.stringify(rows)); console.log(rows.length, 'elements'); await b.close();
})();
