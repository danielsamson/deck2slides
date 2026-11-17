// Lint design-system previews: widows (one-word last line), upper-case text without tracking, text under 20px.
// Usage: node typecheck.cjs <dir holding project/ and compiled.css>
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path');
(async()=>{
 const root=process.argv[2]; const b=await chromium.launch({executablePath:process.env.D2S_CHROMIUM}); const proj=path.resolve(root,'project'); const css=fs.readFileSync(path.resolve(root,'compiled.css'),'utf8');
 let bad=0;
 for(const n of fs.readdirSync(proj+'/components')){ const html=fs.readFileSync(proj+'/components/'+n+'/preview.html','utf8'); const m=/width=(\d+)/.exec(html), h=/height=(\d+)/.exec(html);
  const p=await b.newPage({viewport:{width:m?+m[1]:960,height:+h[1]}});
  fs.writeFileSync(proj+'/_t.html','<base href="file://'+proj+'/"><style>'+css.replace(/url\("fonts/g,'url("file://'+proj+'/fonts')+'</style>'+html);
  await p.goto('file://'+proj+'/_t.html'); await p.waitForTimeout(500);
  const issues=await p.evaluate(()=>{ const out=[];
   for(const e of document.querySelectorAll('body *')){ const tn=[...e.childNodes].filter(x=>x.nodeType===3&&x.textContent.trim()); if(!tn.length) continue;
     const txt=tn.map(x=>x.textContent).join(' ').replace(/\s+/g,' ').trim(); const cs=getComputedStyle(e); const fsz=parseFloat(cs.fontSize);
     const letters=txt.replace(/[^A-Za-z]/g,''); if(letters.length>=3 && txt===txt.toUpperCase()){ const ls=parseFloat(cs.letterSpacing)||0; if(fsz<48 ? ls/fsz<0.08 : ls/fsz<0.01) out.push('UPPERCASE no tracking: '+txt.slice(0,40)); }
     if(fsz<20 && !document.querySelector('.cv')) out.push('under 20px: '+txt.slice(0,30));
     // widow: last line has one word
     const r=document.createRange(); const rects=[]; for(const t of tn){ r.selectNodeContents(t); for(const q of r.getClientRects()) rects.push(q); }
     if(rects.length){ const ys=[...new Set(rects.map(q=>Math.round(q.top/ (fsz*0.5))))]; if(ys.length>=2 && txt.split(' ').length>=3){
       // find words on the last line
       const lastTop=Math.max(...rects.map(q=>q.top)); const words=[]; const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT); let node;
       while(node=w.nextNode()){ const re=/\S+/g; let mm; while(mm=re.exec(node.textContent)){ r.setStart(node,mm.index); r.setEnd(node,mm.index+mm[0].length); const rr=r.getClientRects()[0]; if(rr && Math.abs(rr.top-lastTop)<fsz*0.4) words.push(mm[0]); } }
       if(words.length===1) out.push('WIDOW: '+txt.slice(0,50)+' ... ['+words[0]+']'); } } }
   return out; });
  if(issues.length){ bad+=issues.length; console.log(n, [...new Set(issues)]); }
  await p.close(); }
 fs.unlinkSync(proj+'/_t.html'); console.log('issues',bad); await b.close();})();
