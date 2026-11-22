(() => {
'use strict';
const U='data/market-price-monthly.json',NS='http://www.w3.org/2000/svg';
const modes=[['Flower','#27764f',24],['Pre-rolls','#b5783c',24],['Concentrates','#477d99',90]];
const mon=s=>{const a=s.split('-').map(Number);return a[0]*12+a[1]-1};
const label=s=>{const a=s.split('-').map(Number);return new Date(Date.UTC(a[0],a[1]-1,1)).toLocaleDateString('en-US',{month:'short',year:'numeric',timeZone:'UTC'})};
const E=(tag,attrs,parent)=>{const x=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))x.setAttribute(k,v);parent.append(x);return x};
async function start(){
document.querySelector('[aria-labelledby="reference-title"]')?.remove();
document.getElementById('history-details')?.remove();
const heading=document.querySelector('.market-page h1');if(heading)heading.textContent='Market price trends';
const sub=document.getElementById('history-title');if(sub)sub.textContent='Monthly prices per gram';
sub?.closest('section')?.querySelector('p:not([id])')?.remove();
const r=await fetch(U,{cache:'no-store'});if(!r.ok)throw Error('Pricing unavailable');
const raw=(await r.json()).observations||[],pts=raw.filter(v=>Number.isFinite(Number(v.price_per_gram))&&v.month);
const dates=pts.map(v=>v.month).sort();if(!dates.length)throw Error('No prices');
const lo=mon(dates[0]),hi=mon(dates[dates.length-1]),W=1080,H=465,L=65,R=75,T=34,B=65;
const xx=s=>L+(mon(s)-lo)/Math.max(1,hi-lo)*(W-L-R);
const yy=(v,max)=>T+(1-v/max)*(H-T-B);
const wrap=document.getElementById('history-chart');wrap.innerHTML='';wrap.hidden=false;wrap.style.cssText='position:relative;overflow-x:auto;margin-top:12px';
const legend=document.createElement('div');legend.style.cssText='display:flex;gap:22px;flex-wrap:wrap;font-size:13px;font-weight:700;color:#335a45;margin:12px 0';
for(const [name,color]of modes){const item=document.createElement('span');item.style.cssText='display:inline-flex;align-items:center;gap:7px';const line=document.createElement('i');line.style.cssText='display:inline-block;width:20px;height:4px;border-radius:3px;background:'+color;item.append(line,document.createTextNode(name));legend.append(item)}
wrap.append(legend);
const svg=E('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Monthly flower, pre-rolls and concentrate prices per gram'},wrap);svg.style.cssText='width:100%;min-width:600px;height:auto;display:block';
const text=(x,y,s,extra={})=>{const n=E('text',{x,y,fill:'#7b8b80','font-size':11,...extra},svg);n.textContent=s};
for(let i=0;i<=6;i++){const v=6-i,y=T+i*(H-T-B)/6;E('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'#e3ece6'},svg);text(L-10,y+4,'$'+v*4,{'text-anchor':'end'});text(W-R+12,y+4,'$'+v*15)}
for(let m=lo;m<=hi;m++){if(m!==lo&&m!==hi&&(m-lo)%3)continue;const year=Math.floor(m/12),month=m%12+1,k=year+'-'+String(month).padStart(2,'0');const x=xx(k);E('line',{x1:x,x2:x,y1:T,y2:H-B,stroke:'#eef2ef'},svg);text(x,H-B+24,label(k),{'text-anchor':'middle'})}
text(L,T-16,'Flower / Pre-rolls · $/g');text(W-R,T-16,'Concentrates · $/g',{'text-anchor':'end'});
for(const [name,color,max]of modes){const a=pts.filter(p=>p.category===name).sort((p,q)=>p.month.localeCompare(q.month));if(!a.length)continue;const d=a.map((p,i)=>(i?'L':'M')+xx(p.month).toFixed(2)+','+yy(Number(p.price_per_gram),max).toFixed(2)).join(' ');
E('path',{d,fill:'none',stroke:color,'stroke-width':3.5,'stroke-linecap':'round','stroke-linejoin':'round'},svg);
for(const p of a){const c=E('circle',{cx:xx(p.month),cy:yy(Number(p.price_per_gram),max),r:5,fill:'#fff',stroke:color,'stroke-width':2.5},svg);E('title',{},c).textContent=name+' · '+label(p.month)+' · $'+Number(p.price_per_gram).toFixed(2)+'/g'}}
document.getElementById('history-status').textContent='';
}
start().catch(()=>{document.getElementById('history-status').textContent='Price history temporarily unavailable.'});
})();
