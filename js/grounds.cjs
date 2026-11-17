// Render soft-light "ground" images from configs: base colour, blobs (position, radius, colour, strength), grain.
// Usage: node grounds.cjs <configs.json> <outdir>    configs: {name: {base, blend:'normal'|'screen', grain:0..1, blobs:[{x,y,r,c,a}]}}  x,y,r in canvas fractions (r of the width)
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const [cfgf, out] = process.argv.slice(2); const cfg = JSON.parse(fs.readFileSync(cfgf, 'utf8')); fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch(process.env.D2S_CHROMIUM ? { executablePath: process.env.D2S_CHROMIUM } : {}); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const [name, c] of Object.entries(cfg)) {
    const url = await p.evaluate(({ c }) => {
      const cv = document.createElement('canvas'); cv.width = 1920; cv.height = 1080; const g = cv.getContext('2d');
      g.fillStyle = c.base; g.fillRect(0, 0, 1920, 1080); g.globalCompositeOperation = c.blend === 'screen' ? 'screen' : 'source-over';
      for (const o of c.blobs) { const x = o.x * 1920, y = o.y * 1080, r = o.r * 1920; const gr = g.createRadialGradient(x, y, 0, x, y, r);
        const rgb = o.c; gr.addColorStop(0, rgb + Math.round(o.a * 255).toString(16).padStart(2, '0')); gr.addColorStop(0.55, rgb + Math.round(o.a * 0.35 * 255).toString(16).padStart(2, '0')); gr.addColorStop(1, rgb + '00');
        g.fillStyle = gr; g.save(); if (o.sx) { g.translate(x, y); g.scale(o.sx, 1); g.translate(-x, -y); } g.fillRect(0, 0, 1920, 1080); g.restore(); }
      g.globalCompositeOperation = 'source-over';
      if (c.grain) { const im = g.getImageData(0, 0, 1920, 1080), d = im.data; for (let i = 0; i < d.length; i += 4) { const n = (Math.random() - 0.5) * 255 * c.grain; d[i] += n; d[i + 1] += n; d[i + 2] += n; } g.putImageData(im, 0, 0); }
      return cv.toDataURL('image/jpeg', 0.9);
    }, { c });
    fs.writeFileSync(path.join(out, name + '.jpg'), Buffer.from(url.split(',')[1], 'base64')); console.log(name);
  }
  await b.close();
})();
