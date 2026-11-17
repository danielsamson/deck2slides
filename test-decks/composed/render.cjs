const {chromium}=require('playwright'); const fs=require('fs'); const D=process.argv[2];
(async()=>{const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1920,height:1080}});
const deck=JSON.parse(fs.readFileSync(D+'/deck.json','utf8')); const css=fs.readFileSync(D+'/deck.css','utf8');
const links=Object.values(deck.faces).map(f=>`<link rel="stylesheet" href="${f.href}">`).join('');
for(const id of deck.order){const html=fs.readFileSync(`${D}/slides/${id}.html`,'utf8');
 fs.writeFileSync(`${D}/${id}.page.html`,`<html><head>${links}<style>*{margin:0;box-sizing:border-box}${css}aside{display:none}section{position:relative;width:1920px;height:1080px;overflow:hidden}</style></head><body>${html}</body></html>`);
 await pg.goto('file://'+D+`/${id}.page.html`); await pg.waitForTimeout(800); await pg.screenshot({path:`${D}/${id}.png`});}
await b.close();})();
