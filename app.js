(()=>{'use strict';const $=id=>document.getElementById(id);const key='mntrees_listings_v1',snapkey='mntrees_snapshots_v1';let strainGenetics=[],listings=[],snapshots=[],localOverride=false,trackedStoreTargets=null,retailerDirectory=[],offerHistory={previous:null,current:null};try{listings=JSON.parse(localStorage.getItem(key)||'[]');localOverride=localStorage.getItem('mntrees_local_override')==='yes';if(!localOverride)listings=[];snapshots=JSON.parse(localStorage.getItem(snapkey)||'[]');offerHistory=JSON.parse(localStorage.getItem('mntrees_offer_history_v1')||'{"previous":null,"current":null}')}catch{}const publicSnapshot=fetch('./data/site-data.json',{cache:'no-store'}).then(async response=>{if(!response.ok)throw Error('Unified site data unavailable');const data=await response.json();if(data.schema_version!==1||!Array.isArray(data.catalog)||!Array.isArray(data.retailers))throw Error('Invalid unified site data');return data});const money=n=>Number.isFinite(n)?'$'+n.toFixed(2):'—';const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function msg(s){$('message').textContent=s;$('message').hidden=false;setTimeout(()=>{$('message').hidden=true},6000)}function parseCSV(raw){const rows=[];let row=[],cell='',q=false;for(let i=0;i<raw.length;i++){const c=raw[i];if(q&&c==='"'&&raw[i+1]==='"'){cell+='"';i++}else if(c==='"'){q=!q}else if(!q&&c===','){row.push(cell);cell=''}else if(!q&&(c==='\n'||c==='\r')){if(c==='\r'&&raw[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x.trim()))rows.push(row);row=[];cell=''}else cell+=c}row.push(cell);if(row.some(x=>x.trim()))rows.push(row);if(!rows.length)return[];const heads=rows.shift().map((x,i)=>(i===0?x.replace(/^﻿/,''):x).trim().toLowerCase());return rows.map(r=>Object.fromEntries(heads.map((h,i)=>[h,r[i]||''])))}function norm(o,i){return {id:String(o.id||i),retailer:String(o.retailer||o.store||'').trim(),retailer_id:String(o.retailer_id||'').trim(),strain:String(o.strain||o.product_name||'').trim(),master_strain:String(o.master_strain||'').trim(),strain_match_status:String(o.strain_match_status||'').trim(),brand:String(o.brand||'').trim(),brand_family:String(o.brand_family||o.brand||'').trim(),product_family_decision:String(o.product_family_decision||'').trim(),reviewed_identity:o.reviewed_identity===true,pack_count:o.pack_count,product_variant:String(o.product_variant||'').trim(),raw_scanned_product_name:o.reviewed_identity?String(o.raw_scanned_product_name||'').trim():'',product_name:String(o.product_name||'').trim(),product_family:String(o.product_family||o.strain||'').trim(),category:String(o.category||'').trim(),package_g:Number(o.package_g||o.grams||0),price:Number(o.price||0),analytics_price:Number(o.analytics_price||o.price||0),city:String(o.city||'').trim(),state:String(o.state||'MN').trim(),url:String(o.url||'').trim(),checked_at:String(o.checked_at||'').trim(),address:String(o.address||'').trim(),strain_type:String(o.strain_type||o.strainType||o.classification||'').trim(),source_method:String(o.source_method||''),availability_status:String(o.availability_status||'listed')}}function valid(o){return o.retailer&&o.strain&&Number.isFinite(o.price)&&o.price>0}function persist(){localStorage.setItem(key,JSON.stringify(listings));localStorage.setItem('mntrees_local_override','yes');localOverride=true}function choices(id,vals){const el=$(id),old=el.value;el.replaceChildren(new Option('All '+({category:'categories',brand:'brands',store:'retailers',size:'sizes',strainType:'strain types'}[id]),''));[...new Set(vals.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b))).forEach(x=>el.add(new Option(x,x)));el.value=[...el.options].some(o=>o.value===old)?old:''}function metricValues(source=listings){
 const visible=source.filter(x=>catalog.typeOf(x));
 const active=visible.filter(x=>x.availability_status!=='coming_soon');
 const flower=active.filter(x=>catalog.typeOf(x)==='Flower');
 const flowerPriced=flower.filter(x=>Number.isFinite(x.package_g)&&x.package_g>0&&Number.isFinite(x.price)&&x.price>0);
 const eighth=flower.filter(x=>x.package_g===3.5);
 const ounce=flower.filter(x=>x.package_g===28);
 const preroll=active.filter(x=>/pre.?roll/i.test(x.category)&&x.package_g===1);
 const concentrates=active.filter(x=>catalog.typeOf(x)==='Concentrates'&&Number.isFinite(x.package_g)&&x.package_g>0&&Number.isFinite(x.price)&&x.price>0);
 const effective=x=>Number.isFinite(x.analytics_price)&&x.analytics_price>0?x.analytics_price:x.price;
 const avg=a=>a.length?a.reduce((v,x)=>v+effective(x),0)/a.length:null;
 return {visible,flowerPriced,eighth,ounce,preroll,concentrates,
   values:[flowerPriced.length?flowerPriced.reduce((v,x)=>v+effective(x)/x.package_g,0)/flowerPriced.length:null,avg(eighth),avg(ounce),avg(preroll),
     (eighth.length+ounce.length)?[...eighth,...ounce].reduce((v,x)=>v+effective(x)/x.package_g*453.592,0)/(eighth.length+ounce.length):null,concentrates.length?concentrates.reduce((v,x)=>v+effective(x)/x.package_g,0)/concentrates.length:null]};
}
function metrics(filtered){
 const data=metricValues(filtered);
 const fields=[['Overall flower average / g',data.values[0],data.flowerPriced.length+' flower listings · excludes pre-rolls · mean of listing $/g'],
 ['Average eighth (3.5 g)',data.values[1],data.eighth.length+' qualifying listings'],
 ['Average ounce (28 g)',data.values[2],data.ounce.length+' qualifying listings'],
 ['1g preroll average',data.values[3],data.preroll.length+' qualifying listings'],
 ['Flower pound equivalent',data.values[4],data.eighth.length+' eighths + '+data.ounce.length+' ounces · extrapolated'],
 ['Concentrates average / g',data.values[5],data.concentrates.length+' weight-verified concentrate listings · mean of SKU $/g']];
 const dated=snapshots.filter(x=>x&&Array.isArray(x.metrics)&&x.metrics.length===4&&x.date);
 const current=dated.length?dated[dated.length-1]:null;
 const prior=dated.length>1?dated[dated.length-2]:null;
 const comparable=Boolean(current&&prior&&current.date!==prior.date&&!($('search').value.trim()||['category','brand','store','size','strainType'].some(id=>$(id).value)));
 const trend=i=>{
   if(!comparable)return '';
   const older=Number(prior.metrics[i]),newer=Number(current.metrics[i]);
   if(!(Number.isFinite(older)&&older>0&&Number.isFinite(newer)&&newer>0))return '';
   const change=(newer-older)/older*100;
   const arrow=Math.abs(change)<.05?'→':change>0?'↑':'↓';
   const cls=Math.abs(change)<.05?'trend-flat':change>0?'trend-up':'trend-down';
   const label=(change>0?'+':'')+change.toFixed(1)+'%';
   return '<span class="trend-line '+cls+'" title="'+esc('Change between saved snapshots: '+prior.date+' and '+current.date)+'" aria-label="'+esc('Price trend '+label)+'">'+arrow+' '+esc(label)+'</span>';
 };
 $('metrics').innerHTML=fields.map((x,i)=>'<div class="metric"><span>'+esc(x[0])+'</span><strong>'+money(Number.isFinite(x[1])?x[1]:NaN)+'</strong><span>'+esc(x[2])+'</span>'+(i===0?'':trend(i-1))+'</div>').join('');
 $('heroCount').textContent=data.visible.length.toLocaleString()+' listings';
 $('heroStores').textContent=new Set(data.visible.map(x=>x.retailer)).size+' retailers with advertised offers'+(retailerDirectory.length?' · '+retailerDirectory.length+' retailers in directory':'')+(trackedStoreTargets?' · '+trackedStoreTargets+' menu URLs monitored':'')+' · '+(current?'Last snapshot '+current.date:'No comparable trend snapshot');
 $('dataState').textContent=listings.length?(localOverride?'Local test import (this browser only)':'Published menu snapshot · not live inventory'):'Waiting for verified retailer data';
 $('snapshotLabel').textContent=listings.length?'Based on '+data.visible.length.toLocaleString()+' matching menu listings · updates with filters':'Based on published advertised menu prices';
 $('trendHelp').textContent=comparable?'↑ Price increase · ↓ Price decrease · Compared with previous dated snapshot (this browser)':'Price trends appear after two dated, comparable metric snapshots.';
}
function geneticsFor(name){
 const key=value=>String(value||'').trim().toLowerCase().replace(/^the soap$/, 'soap');
 return strainGenetics.filter(entry=>key(entry.strain)===key(name));
}
// Display-only approximate reference; never alters approved strain or retailer identities.
function relatedGenetics(name){
 const normalize=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
 const tokens=normalize(name).split(' ').filter(Boolean);
 const drop=new Set(['sour','og','kush','haze','purple','blue','black','white','red','green','pink','gold','golden','silver','orange']);
 const stem=tokens.filter(x=>!drop.has(x)).join(' ');
 if(!stem||stem===tokens.join(' ')||stem.length<4)return null;
 const matches=strainGenetics.filter(x=>normalize(x.strain)===stem&&(x.parent1||x.parent2)&&x.source_url&&/^https:\/\//i.test(x.source_url));
 return matches.length===1?matches[0]:null;
}
function floweringEstimate(name,entries){
 const specific=entries.find(x=>x.flowering_time&&x.source_url&&/^https:\/\//i.test(x.source_url));
 if(specific)return String(specific.flowering_time);
 const selected=entries.find(x=>x.classification||x.indica_sativa);
 const classification=String(selected?.classification||selected?.indica_sativa||strainCardTypes[strainCardKey(name)]||'').toLowerCase();
 if(!classification)return '';
 return classification.includes('sativa')&&!classification.includes('indica')?'10–16 weeks (typical estimate)':'8–10 weeks (typical estimate)';
}
function geneticsSummary(name){
 const entries=geneticsFor(name);
 const withParents=entries.find(x=>x.parent1||x.parent2);
 const related=withParents?null:relatedGenetics(name);
 return {entries,withParents,related};
}
publicSnapshot.then(data=>data.strain_genetics).then(rows=>{strainGenetics=Array.isArray(rows)?rows:[];render()}).catch(()=>{});
const catalog=window.MNtreesCatalog;
const redwoodBrand = 'Redwood County Weed Management';
const redwoodLibrary = 'https://www.redwoodcoweed.com/strains';
let redwoodStrains = {};
const redwoodKey = name => String(name || '').normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
publicSnapshot.then(data => data.rcwm_strains).then(data => {
 redwoodStrains = data.strains || {};
 render();
}).catch(() => {});
let strainCardTypes={};
const strainCardKey=name=>String(name||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
function reviewedTypeFor(name){
 const key=strainCardKey(name);
 const reviewed=strainCardTypes[key]||reviewedStrainTypes.get(key);
 if(reviewed)return strainClass(reviewed);
 // The genetics tab is a secondary exact-name source, never an approximate lineage match.
 const genetics=[...new Set(geneticsFor(name).map(x=>strainClass(x.classification||x.indica_sativa)).filter(Boolean))];
 return genetics.length===1?genetics[0]:'';
}
function strainCardBadge(name, offers=[]){
 const direct=reviewedTypeFor(name);
 const candidates=[...new Set(offers.map(o=>strainClass(o.displayStrainType)).filter(Boolean))];
 const type=direct||(candidates.length===1?candidates[0]:'');
 const code=type.includes('Hybrid')?'H':type==='Sativa'?'S':type==='Indica'?'I':'';
 const label=type||'';
 return code?'<span class="strain-type-badge strain-type-'+code.toLowerCase()+'" title="'+esc(label)+'" aria-label="'+esc(label)+'">'+code+'</span>':'';
}
publicSnapshot.then(data=>data.strain_types).then(data=>{
 strainCardTypes=data&&typeof data==='object'&&!Array.isArray(data)?data:{};
 render();
}).catch(()=>{});
function renderComparisons(input){
 const groups=catalog.groupOffers(input);
 const active=o=>o.availability_status!=='coming_soon';
 const best=g=>Math.min(...g.offers.filter(active).map(o=>o.price),Infinity);
 const priceSorted=Boolean(retailerLink);
 if(priceSorted)groups.sort((a,b)=>(best(a)-best(b))||a.strain.localeCompare(b.strain));
 $('count').textContent=groups.length.toLocaleString()+' strains';
 $('checked').textContent=input.length.toLocaleString()+' advertised retailer offers across '+groups.length+' strain cards';
 $('comparisonCount').textContent=priceSorted ? retailerLink.label+' · Lowest advertised price first' : groups.filter(g=>new Set(g.offers.filter(active).map(o=>o.retailer)).size>1).length+' strains listed at multiple retailers';
 const cards=groups.map(g=>{
  const offers=[...g.offers].sort((a,b)=>Number(!active(a))-Number(!active(b))||a.price-b.price||a.retailer.localeCompare(b.retailer));
  const subtype=g.type==='Preroll'?'Pre-Rolls':g.type==='Flower'?'Flower':g.type==='Mixed forms'?'Multiple forms':'Concentrates';
  const detail=g.size;
  const renderOffer=o=>{
    let offerTrend='';
    const prev=offerHistory&&offerHistory.previous&&offerHistory.previous.prices&&offerHistory.previous.prices[o.id];
    const curr=offerHistory&&offerHistory.current&&offerHistory.current.prices&&offerHistory.current.prices[o.id];
    if(Array.isArray(prev)&&Array.isArray(curr)&&Number(prev[1])===Number(curr[1])&&Number(prev[0])>0&&Number(curr[0])>0){
      const delta=Number(curr[0])-Number(prev[0]);
      if(Math.abs(delta)>=.005){
        const up=delta>0;
        offerTrend='<span class="trend-line '+(up?'trend-up':'trend-down')+'" title="Compared with prior published catalog captured in this browser" aria-label="Advertised price '+(up?'increased':'decreased')+' by '+money(Math.abs(delta))+'">'+(up?'↑':'↓')+' '+(up?'+':'−')+money(Math.abs(delta))+'</span>';
      }
    }
    const link=/^https:\/\//i.test(o.url)?'<a class="offer-link" href="'+esc(o.url)+'" target="_blank" rel="noopener noreferrer">Check retailer menu ›</a>':'<span class="offer-link unavailable">Menu link unavailable</span>';
    const ppg=o.pack.total>0?money(o.price/o.pack.total)+'/g':'Price per gram unavailable';
    const note=o.pack.inconsistent?' <span class="offer-warning">Weight needs review</span>':'';
    const coming=active(o)?'':' <span class="offer-warning">Coming soon</span>';
    const matchKey=v=>String(v||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
    const storeMatches=retailerDirectory.filter(store=>[store.name,store.legal_name].some(n=>matchKey(n)===matchKey(o.retailer)));
    const store=storeMatches.length===1?storeMatches[0]:null;
    const address=store&&String(store.map_address||store.address||'').trim();
    const locationPreview=address?'<button type="button" class="retailer-preview-trigger" data-retailer-address="'+esc(address)+'" data-retailer-name="'+esc(o.retailer)+'" aria-label="Preview location of '+esc(o.retailer)+'">'+esc(o.retailer)+' <span class="location-hint">⌖ Map</span></button>':'<span class="compact-retailer">'+esc(o.retailer)+'</span>';
    return '<div class="compact-offer"><div class="compact-offer-meta">'+esc(o.displayBrand)+' · '+esc(o.displayType)+(o.product_variant?' · '+esc(o.product_variant):'')+'</div><div class="compact-offer-main"><div class="compact-retailer-wrap">'+locationPreview+coming+'</div><div class="compact-price">'+money(o.price)+offerTrend+'</div></div><div class="compact-offer-main compact-subline"><span>'+esc(o.city||'Minnesota')+(o.pack.total?' · '+esc(String(o.pack.total))+' g':' · weight not listed')+(o.reviewed_identity&&o.pack.packLabel?' · '+esc(o.pack.packLabel):'')+'</span><span>'+esc(ppg)+'</span></div>'+note+link+'</div>';
  };
  const summary=geneticsSummary(g.strain);
  const hasGeneticsReference=summary.entries.some(x=>x.parent1||x.parent2||x.classification||x.indica_sativa||x.terpenes||x.children||x.breeder||x.source_url);
  const hasRedwoodReference=Boolean(redwoodStrains[redwoodKey(g.strain)]);
  const genericProfile=!hasGeneticsReference&&!summary.related&&!hasRedwoodReference;
  const geneticsHtml=genericProfile?'':'<div class="strain-genetics-brief">'+
   (summary.withParents?'<span>Lineage</span> '+esc([summary.withParents.parent1,summary.withParents.parent2].filter(Boolean).join(' × ')):
   summary.related?'<span>Related strain</span> '+esc(summary.related.strain)+'*':
   '<span>Origin</span> Possible custom cross / locally bred variation')+'</div>';
  const visibleOffers=offers.slice(0,3).map(renderOffer).join('');
  const extraOffers=offers.length>3?'<details class="more-stores"><summary><span class="more-plus" aria-hidden="true">+</span><span class="more-label">Show '+(offers.length-3)+' more '+(offers.length-3===1?'offer':'offers')+'</span><span class="more-less">Show fewer offers</span></summary><div class="more-stores-content">'+offers.slice(3).map(renderOffer).join('')+'</div></details>':'';
   const brands=[...new Set(g.offers.map(o=>o.displayBrand).filter(x=>x!=='Brand not confirmed'))];
   const brandSummary=brands.length>1?brands.length+' brands · ':'';
   const redwoodProfile = hasRedwoodReference ? ' data-redwood-profile' : '';
   return '<article class="compact-card"><div class="compact-card-header"><div class="compact-brand">STRAIN</div><h3>'+(genericProfile?'<span class="strain-name-static">'+esc(g.strain)+'</span>':'<button type="button" class="strain-profile-trigger" data-strain-name="'+esc(g.strain)+'"'+redwoodProfile+' aria-label="View genetics and strain profile for '+esc(g.strain)+'">'+esc(g.strain)+' <span aria-hidden="true">↗</span></button>')+strainCardBadge(g.strain,g.offers)+'</h3><p>'+esc(brandSummary+subtype+' / '+detail)+'</p></div>'+geneticsHtml+'<div class="compact-offers">'+visibleOffers+extraOffers+'</div></article>';
 });
 if(priceSorted&&cards.length){
   $('alphabetNav').replaceChildren();
   $('comparisonGroups').innerHTML='<div class="alphabet-grid">'+cards.join('')+'</div>';
   return;
 }
 const buckets=new Map();
 groups.forEach((g,index)=>{
   const letter=/^[A-Z]/i.test(g.strain.trim())?g.strain.trim().charAt(0).toUpperCase():'#';
   if(!buckets.has(letter))buckets.set(letter,[]);
   buckets.get(letter).push(cards[index]);
 });
 const hasFilters=Boolean($('search').value.trim()||['category','brand','store','size','strainType'].some(id=>$(id).value));
 const slug=letter=>letter==='#'?'other':letter.toLowerCase();
 $('alphabetNav').innerHTML=groups.length?'<div class="alphabet-actions"><button type="button" id="expandLetters">Expand all</button><button type="button" id="collapseLetters">Collapse all</button></div><nav class="alphabet-letters" aria-label="Jump to strain letter">'+[...buckets.keys()].map(letter=>'<button type="button" data-letter="'+esc(letter)+'" aria-label="Open strain names beginning with '+esc(letter)+'">'+esc(letter)+'</button>').join('')+'</nav>':'';
 const previews=new Map();
 for(const group of groups){
  const name=String(group.strain||'').trim();
  const letter=/^[A-Z]/i.test(name)?name.charAt(0).toUpperCase():'#';
  if(!previews.has(letter))previews.set(letter,[]);
  if(previews.get(letter).length<5)previews.get(letter).push(name);
 }
 $('comparisonGroups').innerHTML=groups.length?[...buckets.entries()].map(([letter,items])=>{
   const names=previews.get(letter)||[];
   const preview=names.join(' · ')+(items.length>names.length?' · …':'');
   return '<details class="alphabet-section" id="letter-'+slug(letter)+'"'+(hasFilters?' open':'')+'><summary><span class="letter-name">'+esc(letter)+'</span><span class="letter-count">'+items.length+' '+(items.length===1?'strain':'strains')+'</span><span class="alphabet-preview">'+esc(preview)+'</span><span class="letter-toggle" aria-hidden="true">⌄</span></summary><div class="alphabet-grid">'+items.join('')+'</div></details>';
 }).join(''):'<div class="empty">No matching strains. Try resetting the filters.</div>';
}
// A single accessible floating location dialog avoids clipping within compact strain cards.
const strainProfileDialog=document.createElement('dialog');
strainProfileDialog.className='strain-profile-dialog';
strainProfileDialog.setAttribute('aria-label','Strain profile');
document.body.appendChild(strainProfileDialog);
const profileField=(label,value)=>value?'<div class="strain-profile-field"><span>'+label+'</span><strong>'+esc(value)+'</strong></div>':'';
function renderRedwoodProfile(name) {
 const entry = redwoodStrains[redwoodKey(name)];
 if (!entry) return '';
 const days90 = 90 * 24 * 60 * 60 * 1000;
 const today = Date.parse(new Date().toISOString().slice(0, 10));
 const deliveries = (entry.deliveries || []).filter(delivery => {
  const date = Date.parse(delivery.delivered);
  return date <= today && date >= today - days90;
 });
 const deliveryList = deliveries.length ? '<details><summary>Redwood retailer deliveries in the last 90 days (' +
  deliveries.length + ')</summary><p>Delivery history only. Check the retailer menu for current availability.</p><ul>' +
  deliveries.map(delivery => {
   const location = [delivery.city, delivery.state].filter(Boolean).join(', ');
   return '<li>' + esc(delivery.name) + (location ? ' · ' + esc(location) : '') +
    ' · <time datetime="' + esc(delivery.delivered) + '">' + esc(delivery.delivered) + '</time></li>';
  }).join('') + '</ul></details>' : '';
 return '<section class="strain-profile-entry"><p class="strain-profile-breeder">' + redwoodBrand +
  '</p><div class="strain-profile-grid">' + profileField('Strain type', entry.type) +
  profileField('Genetics', entry.genetics) + '</div>' + deliveryList + '<a href="' + redwoodLibrary +
  '" target="_blank" rel="noopener noreferrer">Source: Redwood Strain Library ↗</a></section>';
}
document.addEventListener('click',event=>{
 const trigger=event.target.closest('.strain-profile-trigger');
 if(!trigger)return;
 const name=trigger.dataset.strainName||'';
 const summary=geneticsSummary(name);
 const entries=summary.entries;
 const redwood=redwoodStrains[redwoodKey(name)]?renderRedwoodProfile(name):'';
 const displayEntries=entries.filter(x=>x.parent1||x.parent2||x.classification||x.indica_sativa||x.terpenes||x.children||x.breeder);
 const genetics=displayEntries.map(x=>{
  const parents=[x.parent1,x.parent2].filter(Boolean).join(' × ');
  const children=Array.isArray(x.children)?x.children.join(', '):x.children;
  const terpenes=Array.isArray(x.terpenes)?x.terpenes.join(', '):x.terpenes;
  return '<section class="strain-profile-entry"><div class="strain-profile-grid">'+profileField('Parents',parents)+profileField('Related cultivars',children)+profileField('Type',x.classification||x.indica_sativa)+profileField('Flowering',floweringEstimate(name,entries))+profileField('Terpenes',terpenes)+'</div>'+(x.source_url&&/^https:\/\//i.test(x.source_url)?'<a href="'+esc(x.source_url)+'" target="_blank" rel="noopener noreferrer">Source: '+esc(x.source||'Cultivar reference')+' ↗</a>':'')+'</section>';
 }).join('');
 const approximate=summary.related?'<section class="strain-profile-entry"><div class="strain-profile-grid">'+profileField('Related strain',summary.related.strain+'*')+profileField('Reported lineage',[summary.related.parent1,summary.related.parent2].filter(Boolean).join(' × '))+profileField('Flowering',floweringEstimate(name,entries))+'</div>'+'</section>':'';
 const placeholder='<section class="strain-profile-entry"><div class="strain-profile-grid">'+profileField('Origin','Possible custom cross / locally bred variation')+profileField('Flowering',floweringEstimate(name,entries))+'</div></section>';
 strainProfileDialog.innerHTML='<div class="strain-profile-heading"><div><span class="strain-profile-kicker">STRAIN PROFILE</span><h2>'+esc(name)+'</h2></div><button type="button" class="strain-profile-close" aria-label="Close strain profile">×</button></div>'+(redwood+genetics+(summary.withParents?'':approximate)||placeholder);
 strainProfileDialog.showModal();
});
strainProfileDialog.addEventListener('click',event=>{if(event.target===strainProfileDialog||event.target.closest('.strain-profile-close'))strainProfileDialog.close()});
const storeMatchesForPreview=name=>{const norm=v=>String(v||'').trim().toLowerCase();const matches=retailerDirectory.filter(x=>[x.name,x.legal_name].some(n=>norm(n)===norm(name)));return matches.length===1?matches[0]:null;};
const locationDialog=document.createElement('dialog');
locationDialog.className='retailer-location-dialog';
locationDialog.setAttribute('aria-label','Retailer location preview');
document.body.appendChild(locationDialog);
document.addEventListener('click',event=>{
 const trigger=event.target.closest('.retailer-preview-trigger');
 if(!trigger)return;
 const address=trigger.dataset.retailerAddress||'';
 const name=trigger.dataset.retailerName||'Dispensary';
 if(!address)return;
 locationDialog.innerHTML='<div class="retailer-dialog-heading"><strong>'+esc(name)+'</strong><button type="button" class="retailer-dialog-close" aria-label="Close location preview">×</button></div><p>'+esc(address)+'</p><div id="retailer-dialog-map" class="retailer-dialog-map" role="application" aria-label="Interactive map of '+esc(name)+'"></div><a href="https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(address)+'" target="_blank" rel="noopener noreferrer">Open in Google Maps ↗</a>';
 locationDialog.showModal();
 const mapHost=locationDialog.querySelector('#retailer-dialog-map');
 if(typeof L!=='undefined'){
   if(locationDialog._leafletMap){locationDialog._leafletMap.remove();locationDialog._leafletMap=null;}
   const locationMap=L.map(mapHost,{scrollWheelZoom:true,zoomControl:true}).setView([46.3,-94.4],7);
   locationDialog._leafletMap=locationMap;
   L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap contributors',maxZoom:19}).addTo(locationMap);
   const exact=storeMatchesForPreview(name);
   const known=exact&&['address_verified','rooftop_verified','census_address_range_interpolated'].includes(exact.coordinate_accuracy)&&Number.isFinite(Number(exact.lat))&&Number.isFinite(Number(exact.lng));
   const showPoint=(lat,lng)=>{if(!locationDialog.open)return;locationMap.setView([lat,lng],15);L.marker([lat,lng]).addTo(locationMap).bindPopup(esc(name)+'<br>'+esc(address));};
   if(known)showPoint(Number(exact.lat),Number(exact.lng));
   else fetch('https://geocode-api.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?'+new URLSearchParams({SingleLine:address+', USA',f:'json',outFields:'Match_addr',maxLocations:'1'})).then(r=>r.json()).then(d=>{const p=d.candidates&&d.candidates[0];if(p&&p.score>=90&&p.location)showPoint(p.location.y,p.location.x);else mapHost.insertAdjacentHTML('beforeend','<p class="retailer-map-unresolved">Exact map location unavailable. Use the Google Maps link below.</p>')}).catch(()=>mapHost.insertAdjacentHTML('beforeend','<p class="retailer-map-unresolved">Map lookup unavailable. Use the Google Maps link below.</p>'));
   requestAnimationFrame(()=>locationMap.invalidateSize());
 }

});
locationDialog.addEventListener('click',event=>{if(event.target===locationDialog||event.target.closest('.retailer-dialog-close'))locationDialog.close()});
$('alphabetNav').addEventListener('click',e=>{
 const button=e.target.closest('button');
 if(!button)return;
 const all=[...document.querySelectorAll('.alphabet-section')];
 if(button.id==='expandLetters')all.forEach(x=>x.open=true);
 if(button.id==='collapseLetters')all.forEach(x=>x.open=false);
 if(button.dataset.letter){
   const id='letter-'+(button.dataset.letter==='#'?'other':button.dataset.letter.toLowerCase());
   const section=document.getElementById(id);
   if(section){section.open=true;section.scrollIntoView({behavior:'smooth',block:'start'});}
 }
});
function strainClass(value){
 const s=String(value||'').toLowerCase().trim();
 if(!s)return '';
 if(s.includes('sativa-leaning hybrid'))return 'Sativa-leaning Hybrid';
 if(s.includes('indica-leaning hybrid'))return 'Indica-leaning Hybrid';
 if(s.includes('balanced hybrid'))return 'Balanced Hybrid';
 if(s.includes('hybrid'))return 'Hybrid';
 if(s.includes('sativa'))return 'Sativa';
 if(s.includes('indica'))return 'Indica';
 return '';
}
let reviewedStrainTypes=new Map([['blue dream','Sativa'],['sour diesel','Sativa'],['jelly breath','Indica']]);
function strainTypeFor(o,consensus){
 const key=strainCardKey(o.displayStrain);
 // Use the same authoritative classification for filters, cards, and Top 10.
 // Explicit menu types are fallback evidence, never an override of owner review.
 return reviewedTypeFor(o.displayStrain)||strainClass(o.strain_type)||
   strainClass((o.product_name||'').match(/(?:^|[|,() -])(sativa|indica|hybrid)(?:$|[|,() -])/i)?.[1])||
   consensus.get(key)||'';
}
function reconcileRetailers(){
 const byName=new Map();
 for(const store of retailerDirectory){
  for(const name of [store.name,store.legal_name]){
   const key=String(name||'').trim().toLowerCase();
   if(!key)continue;
   if(!byName.has(key))byName.set(key,[]);
   if(!byName.get(key).includes(store))byName.get(key).push(store);
  }
 }
 for(const item of listings){
  const key=String(item.retailer||'').trim().toLowerCase();
  const matches=byName.get(key)||[];
  // Only rewrite unambiguous identities. Never merge multiple branches under a legal name.
  if(matches.length===1)item.retailer=matches[0].name;
 }
}
const deepLinkParams=new URLSearchParams(window.location.search);
const storeLinkValues=key=>new Set(deepLinkParams.getAll(key).map(value=>value.trim().toLowerCase()).filter(Boolean));
const linkedStoreNames=storeLinkValues('store');
const linkedStoreIds=storeLinkValues('storeId');
const requestedBrand=deepLinkParams.get('brand');
let retailerLink=linkedStoreIds.size||linkedStoreNames.size
 ? {ids:linkedStoreIds,names:linkedStoreNames,label:deepLinkParams.get('retailer')||deepLinkParams.get('store')||'Retailer strains'}
 : null;

function matchesRetailerLink(offer){
 if(!retailerLink)return true;
 const id=offer.retailer_id.toLowerCase();
 if(retailerLink.ids.size&&id)return retailerLink.ids.has(id);
 return retailerLink.names.has(offer.retailer.trim().toLowerCase());
}

function clearRetailerLink(){
 if(!retailerLink)return;
 retailerLink=null;
 const url=new URL(window.location.href);
 for(const key of ['store','storeId','retailer'])url.searchParams.delete(key);
 history.replaceState(history.state,'',url);
}
let brandDeepLinkPending=!!requestedBrand;
let publishedBusinessTags={brands:[],retailers:[]}, publishedBrandDirectory=[];
const classificationKey=name=>String(name||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
function classificationBadges(labels) {
 const unique=[...new Set(labels.filter(label=>['SEA','Corporate','Tribal','Indoor','Outdoor'].includes(label)))];
 return unique.map(label=>'<span class="top-classification-badge top-classification-'+label.toLowerCase()+'" title="'+esc(label)+' classification">'+esc(label)+'</span>').join('');
}
function brandClassification(name) {
 const canonical=classificationKey(MNtreesCatalog.canonicalBrand(name));
 const rows=(publishedBusinessTags.brands||[]).filter(row=>[row.name,row.canonical_name].some(value=>classificationKey(MNtreesCatalog.canonicalBrand(value))===canonical));
 const labels=rows.flatMap(row=>row.verified_tags||[]);
 const directory=publishedBrandDirectory.find(row=>classificationKey(MNtreesCatalog.canonicalBrand(row.name))===canonical || (row.aliases||[]).some(alias=>classificationKey(MNtreesCatalog.canonicalBrand(alias))===canonical));
 const cultivation=directory?.cultivation_type || rows.find(row=>['Indoor','Outdoor'].includes(row.cultivation_type))?.cultivation_type;
 return classificationBadges([...labels,cultivation]);
}
function retailerClassification(id,name) {
 const idKey=classificationKey(id), nameKey=classificationKey(name);
 const records=(publishedBusinessTags.retailers||[]).filter(row=>idKey ? classificationKey(row.id)===idKey : classificationKey(row.name)===nameKey);
 return classificationBadges(records.flatMap(row=>row.verified_tags||[]));
}
function renderTopRetailers(enriched, selectedBrand) {
 const target=$('topStrainsList');
 const byStore=new Map();
 const normValue=v=>String(v||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
 for(const offer of enriched) {
  if(offer.availability_status==='coming_soon'||offer.displayBrand!==selectedBrand)continue;
  const name=String(offer.retailer||'').trim();
  if(!name)continue;
  const retailerId=String(offer.retailer_id||'').trim();
  const storeKey=retailerId ? 'id:'+normValue(retailerId) : 'location:'+normValue([name,offer.city,offer.address].join('|'));
  // Distinguish a brand's strain, product form, package size and variant, but not repeated scans/prices.
  const sku=[offer.product_name||offer.displayStrain||offer.strain,offer.displayStrain||offer.strain,offer.displayType||offer.category,offer.package_g||'',offer.product_variant||'',offer.pack_count||''].map(normValue).join('|');
  if(!sku.replace(/\|/g,''))continue;
  if(!byStore.has(storeKey))byStore.set(storeKey,{name,retailerId,skus:new Set()});
  byStore.get(storeKey).skus.add(sku);
 }
 const ranked=[...byStore.values()].sort((a,b)=>b.skus.size-a.skus.size||a.name.localeCompare(b.name)).slice(0,10);
 if(!ranked.length){target.innerHTML='<p class="muted">No published retailer SKUs available for this brand.</p>';return;}
 target.innerHTML='<ol class="top-strains-ranking">'+ranked.map((item,index)=>'<li class="top-strains-item"><span class="top-strains-rank">'+(index+1)+'</span><button type="button" class="top-strains-link" data-top-retailer="'+esc(item.name)+'" aria-label="Show '+esc(selectedBrand)+' products at '+esc(item.name)+'">'+esc(item.name)+'</button>'+retailerClassification(item.retailerId,item.name)+'<span class="top-strains-count">'+item.skus.size+' '+(item.skus.size===1?'SKU':'SKUs')+'</span></li>').join('')+'</ol>';
}
function renderTopBrands(enriched, selectedRetailer) {
 const target=$('topStrainsList');
 const byBrand=new Map();
 const normValue=v=>String(v||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
 for(const offer of enriched) {
  if(offer.availability_status==='coming_soon')continue;
  if(selectedRetailer==='__retailer_link__' ? !matchesRetailerLink(offer) : offer.retailer!==selectedRetailer)continue;
  const name=String(offer.displayBrand||'').trim();
  if(!name||/^unknown|unbranded|unassigned$/i.test(name))continue;
  const key=normValue(name);
  if(!byBrand.has(key))byBrand.set(key,{name,skus:new Set(),strains:new Set()});
  const item=byBrand.get(key);
  // Count actual unique SKUs, not repeated source captures or prices.
  const sku=[offer.displayStrain||offer.strain,offer.displayType||offer.category,offer.package_g||'',offer.product_variant||'',offer.pack_count||'',offer.product_family_decision||''].map(normValue).join('|');
  if(!sku.replace(/\|/g,''))continue;
  item.skus.add(sku);
  if(offer.displayStrain)item.strains.add(normValue(offer.displayStrain));
 }
 const ranked=[...byBrand.values()].sort((a,b)=>b.skus.size-a.skus.size||b.strains.size-a.strains.size||a.name.localeCompare(b.name)).slice(0,10);
 if(!ranked.length){target.innerHTML='<p class="muted">No named brands in the published offers for this retailer.</p>';return;}
 target.innerHTML='<ol class="top-strains-ranking">'+ranked.map((item,index)=>'<li class="top-strains-item"><span class="top-strains-rank">'+(index+1)+'</span><button type="button" class="top-strains-link" data-top-brand="'+esc(item.name)+'" aria-label="Show '+esc(item.name)+' offers at this retailer">'+esc(item.name)+'</button>'+brandClassification(item.name)+'<span class="top-strains-count">'+item.skus.size+' '+(item.skus.size===1?'SKU':'SKUs')+' <small>· '+item.strains.size+' '+(item.strains.size===1?'strain':'strains')+'</small></span></li>').join('')+'</ol>';
}
function renderTopStrains(enriched){
 const target=$('topStrainsList');
 if(!target)return;
 const byStrain=new Map();
 for(const offer of enriched){
  if(offer.availability_status==='coming_soon')continue;
  const name=String(offer.displayStrain||'').trim();
  const retailer=String(offer.retailer_id||[offer.retailer,offer.city,offer.address].filter(Boolean).join('|')).trim().toLocaleLowerCase();
  if(!name||!retailer)continue;
  const key=name.toLocaleLowerCase();
  if(!byStrain.has(key))byStrain.set(key,{name,retailers:new Set(),offers:0,types:new Set()});
  const item=byStrain.get(key);
  item.retailers.add(retailer);
  item.offers++;
  if(offer.displayStrainType)item.types.add(offer.displayStrainType);
 }
 const ranked=[...byStrain.values()].sort((a,b)=>b.retailers.size-a.retailers.size||b.offers-a.offers||a.name.localeCompare(b.name)).slice(0,10);
 if(!ranked.length){target.innerHTML='<p class="muted">No current published strain offers available for ranking.</p>';return;}
 target.innerHTML='<ol class="top-strains-ranking">'+ranked.map((item,index)=>'<li class="top-strains-item"><span class="top-strains-rank">'+(index+1)+'</span><span class="top-strains-name"><button type="button" class="top-strains-link" data-top-strain="'+esc(item.name)+'" aria-label="Show retailers and prices for '+esc(item.name)+'">'+esc(item.name)+'</button>'+strainCardBadge(item.name,[...item.types].map(displayStrainType=>({displayStrainType})))+'</span><span class="top-strains-count">'+item.retailers.size+' '+(item.retailers.size===1?'retailer':'retailers')+' <small>· '+item.offers+' '+(item.offers===1?'offer':'offers')+'</small></span></li>').join('')+'</ol>';
}
$('topStrainsList').addEventListener('click',event=>{
 const retailerButton=event.target.closest('button[data-top-retailer]');
 if(retailerButton){
  const store=retailerButton.dataset.topRetailer||'';
  if(!store)return;
  clearRetailerLink();
  $('store').value=store;
  render();
  $('comparisonGroups').scrollIntoView({behavior:'smooth',block:'start'});
  return;
 }
 const brandButton=event.target.closest('button[data-top-brand]');
 if(brandButton){
  const brand=brandButton.dataset.topBrand||'';
  if(!brand)return;
  $('brand').value=brand;
  render();
  $('comparisonGroups').scrollIntoView({behavior:'smooth',block:'start'});
  return;
 }
 const button=event.target.closest('button[data-top-strain]');
 if(!button)return;
 const strain=button.dataset.topStrain||'';
 if(!strain)return;
 clearRetailerLink();
 $('search').value=strain;
 $('comparisonSearch').value=strain;
 ['category','brand','store','size','strainType'].forEach(id=>$(id).value='');
 render();
 $('comparisonGroups').scrollIntoView({behavior:'smooth',block:'start'});
});
function render(){
 reconcileRetailers();
 const enriched=listings.map(catalog.enriched).filter(x=>x.displayType);
 const evidence=new Map();
 for(const o of enriched){
  if(!['Flower','Preroll'].includes(o.displayType))continue;
  const type=strainClass(o.strain_type)||strainClass(o.product_name.match(/(?:^|[|,() -])(sativa|indica|hybrid)(?:$|[|,() -])/i)?.[1]);
  if(!type)continue;
  const key=String(o.displayStrain||'').toLowerCase().trim();
 if(!key)continue;
  if(!evidence.has(key))evidence.set(key,new Set());
  evidence.get(key).add(type);
 }
 const consensus=new Map([...evidence].filter(([,types])=>types.size===1).map(([key,types])=>[key,[...types][0]]));
 for(const o of enriched)o.displayStrainType=['Flower','Preroll'].includes(o.displayType)?strainTypeFor(o,consensus):'';

 const category=$("category"),selectedCategory=category.value;
 category.replaceChildren(new Option("All types",""),...["Flower","Preroll","Concentrates"].map(x=>new Option(x,x)));
 category.value=["Flower","Preroll","Concentrates"].includes(selectedCategory)?selectedCategory:"";
 choices('brand',enriched.map(x=>x.displayBrand));
 if(brandDeepLinkPending && enriched.length){
  const normalizeBrand=x=>String(x||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLocaleLowerCase();
  const requested=normalizeBrand(catalog.canonicalBrand(requestedBrand));
  const matching=[...$('brand').options].find(o=>o.value && normalizeBrand(o.value)===requested);
  if(matching){$('brand').value=matching.value;brandDeepLinkPending=false;}
 }
 choices('store',enriched.map(x=>x.retailer));
 if(retailerLink){
  const picker=$('store');
  picker.add(new Option(retailerLink.label,'__retailer_link__'),1);
  picker.value='__retailer_link__';
 }
 choices('size',enriched.map(x=>catalog.filterSize(x)));
 const strainTypeSelect=$('strainType'),selectedStrainType=strainTypeSelect.value;
 const strainOptions=['Sativa','Indica','Hybrid','Sativa-leaning Hybrid','Indica-leaning Hybrid','Balanced Hybrid'];
 strainTypeSelect.replaceChildren(new Option('All strain types',''),...strainOptions.map(x=>new Option(x,x)));
 strainTypeSelect.value=strainOptions.includes(selectedStrainType)?selectedStrainType:'';
 const selectedBrand=$('brand').value;
 const selectedRetailer=retailerLink?'__retailer_link__':$('store').value;
 const retailerLabel=retailerLink?retailerLink.label:selectedRetailer;
 const topTitle=$('topStrainsTitle');
 const topSubtitle=document.querySelector('.top-strains-subtitle');
 const topNote=document.querySelector('.top-strains-note');
 if(selectedRetailer){
  topTitle.textContent='Top 10 Brands at '+retailerLabel;
  topSubtitle.textContent='Ranked by distinct advertised SKUs carried by this retailer, across its published menu offers.';
  topNote.textContent='Advertised menu offers only; not verified live inventory. Repeated scans do not increase brand rankings.';
  renderTopBrands(enriched,selectedRetailer);
 }else if(selectedBrand){
  topTitle.textContent='Top 10 Retailers for '+selectedBrand;
  topSubtitle.textContent='Ranked by the number of distinct published SKUs for this brand at each retailer.';
  topNote.textContent='Advertised menu SKUs, not verified live inventory. Duplicate scans do not increase SKU counts.';
  renderTopRetailers(enriched,selectedBrand);
 }else{
  topTitle.textContent='Top 10 Most Available Strains';
  topSubtitle.textContent='Ranked by the number of distinct retailers advertising each strain across tracked Minnesota menus.';
  topNote.textContent='Advertised listings only; live inventory is not verified. Different sizes, brands, and product forms at the same retailer count as one retailer.';
  renderTopStrains(enriched);
 }
 const term=$('search').value.trim().toLowerCase();
 const filtered=enriched.filter(o=>[o.displayStrain,o.displayBrand,o.retailer,o.city,o.strain,o.product_name,[o.displayStrain,o.product_variant].join(' ')].some(v=>String(v||'').toLowerCase().includes(term))
   &&(!$('category').value||o.displayType===$('category').value)
   &&(!$('brand').value||o.displayBrand===$('brand').value)
   &&(retailerLink ? matchesRetailerLink(o) : (!$('store').value||o.retailer===$('store').value))
   &&(!$('size').value||catalog.filterSize(o)===$('size').value)
   &&(!$('strainType').value||(o.displayStrainType===$('strainType').value||($('strainType').value==='Hybrid'&&o.displayStrainType.includes('Hybrid')))));
 renderComparisons(filtered);
 metrics(filtered);
}
['search','category','brand','size','strainType'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',render));
$('store').addEventListener('change',()=>{
 clearRetailerLink();
 render();
});
$('reset').addEventListener('click',()=>{
 clearRetailerLink();
 $('search').value='';
 $('comparisonSearch').value='';
 ['category','brand','store','size','strainType'].forEach(id=>$(id).value='');
 render();
});
function exportCSV(){const heads=['id','retailer','strain','brand','category','package_g','price','city','state','url','checked_at','address','product_variant'];return [heads.join(','),...listings.map(x=>heads.map(k=>'"'+String(x[k]??'').replace(/"/g,'""')+'"').join(','))].join('\r\n')}function download(name,content,type){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([content],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}$('exportBtn').addEventListener('click',()=>download('mntrees-listings.csv',exportCSV(),'text/csv'));$('snapshotBtn').addEventListener('click',()=>{if(!listings.length)return msg('No published listings to snapshot.');const values=metricValues().values;snapshots.push({date:new Date().toISOString(),count:listings.length,metrics:values});snapshots=snapshots.slice(-48);localStorage.setItem(snapkey,JSON.stringify(snapshots));render();msg('Dated price metrics saved in this browser. Trend arrows appear when a second comparable snapshot exists.')});$('clearBtn').addEventListener('click',()=>{if(!confirm('Clear locally saved listing data?'))return;listings=[];localStorage.removeItem(key);localStorage.removeItem('mntrees_local_override');localOverride=false;loadPublished();msg('Local import cleared; restored the published snapshot.')});$('demoBtn').addEventListener('click',()=>msg('Demo data is intentionally not bundled. Import verified listings to avoid misleading public prices.'));async function loadPublished(){
 try{const snapshot=await publicSnapshot;const values=snapshot.retailers;retailerDirectory=Array.isArray(values)?values:[];publishedBusinessTags=snapshot.business_tags||{brands:[],retailers:[]};publishedBrandDirectory=Array.isArray(snapshot.brands)?snapshot.brands:[]}catch{}
 try{const types=(await publicSnapshot).strain_types;if(types&&typeof types==='object'&&!Array.isArray(types))reviewedStrainTypes=new Map(Object.entries(types).filter(([k,v])=>k&&['Sativa','Indica','Hybrid','Balanced Hybrid','Sativa-leaning Hybrid','Indica-leaning Hybrid'].includes(v)));}catch{}
// Always load the current public feed; stale local imports must not override published corrections.
try{const dat=(await publicSnapshot).catalog;if(!Array.isArray(dat)||!dat.length)throw Error('Invalid unified catalog');listings=dat.map(norm).filter(valid);localOverride=false;try{localStorage.removeItem('mntrees_local_override')}catch{}
 // Preserve comparable price history when a new published catalog is observed.
 // A new signature is recorded once per browser; reloads do not create fake trends.
 const signature=dat.reduce((h,o)=>{
   const value=String(o.id||'')+'|'+String(o.price||'')+'|'+String(o.package_g||'')+';';
   for(let i=0;i<value.length;i++)h=Math.imul(h^value.charCodeAt(i),16777619);
   return h;
 },2166136261).toString(16);
 const newPrices=Object.fromEntries(listings.filter(x=>x.id&&Number.isFinite(x.price)&&x.price>0).map(x=>[x.id,[x.price,x.package_g]]));
 if(!offerHistory||!offerHistory.current||offerHistory.current.signature!==signature){
   offerHistory={previous:offerHistory&&offerHistory.current||null,current:{signature,date:new Date().toISOString(),prices:newPrices}};
   try{localStorage.setItem('mntrees_offer_history_v1',JSON.stringify(offerHistory))}catch{}
 }
 if(!snapshots.some(x=>x.source==='published_catalog'&&x.signature===signature)){
   snapshots.push({date:new Date().toISOString(),source:'published_catalog',signature,count:listings.length,metrics:metricValues().values});
   snapshots=snapshots.slice(-48);
   try{localStorage.setItem(snapkey,JSON.stringify(snapshots))}catch{}
 }
 localOverride=false}catch{}try{const v=(await publicSnapshot).manifest;trackedStoreTargets=Number(v.retailer_scan_targets)||null}catch{}render()}async function loadReviewCandidates(){try{const response=await fetch('./data/review_candidates.json',{cache:'no-store'});if(!response.ok)throw Error('Review feed unavailable');const body=await response.json();if(!Array.isArray(body.candidates))throw Error('Invalid feed');const records=body.candidates;const decisionsKey='mntrees_review_decisions_v1';let decisions={};try{decisions=JSON.parse(localStorage.getItem(decisionsKey)||'{}');if(!decisions||typeof decisions!=='object'||Array.isArray(decisions))decisions={}}catch{decisions={}}const allowed=['pending','verify','hold','reject'];const statusText={pending:'Not reviewed',verify:'Approve for verification',hold:'Needs correction',reject:'Exclude from review queue'};const renderReview=()=>{const choice=$('reviewStatus').value;const visible=records.filter(x=>!choice||(choice==='coming'?String(x.menu_status).startsWith('coming'):x.menu_status===choice));const marked=records.filter(x=>decisions[x.candidate_id]&&decisions[x.candidate_id]!=='pending').length;$('reviewCount').textContent=visible.length+' of '+records.length+' candidates · '+marked+' reviewed';$('reviewResults').innerHTML=visible.map(x=>{const status=String(x.menu_status||'unknown').replace(/_/g,' ');const grams=Number(x.advertised_total_grams),price=Number(x.advertised_price_usd);const weight=grams>0&&x.menu_status!=='coming_soon_weight_ambiguous'?grams+'g':'weight needs review';const state=allowed.includes(decisions[x.candidate_id])?decisions[x.candidate_id]:'pending';const opts=allowed.map(v=>'<option value="'+v+'"'+(state===v?' selected':'')+'>'+statusText[v]+'</option>').join('');return '<article class="listing"><span class="tag">'+esc(x.category||'Other')+'</span><h3>'+esc(x.strain||x.advertised_product_name)+'</h3><p>'+esc(x.advertised_brand||'Brand needs review')+' · '+esc(x.retailer)+'</p><p>'+esc(weight)+' · '+esc(x.city)+'</p><div class="price">'+(Number.isFinite(price)&&price>0?money(price):'Price needs review')+'</div><p class="reviewstatus">'+esc(status)+' · review only, not verified stock</p><label class="reviewdecision">My decision <select data-candidate-id="'+esc(x.candidate_id)+'" aria-label="Review decision for '+esc(x.strain||x.advertised_product_name)+'">'+opts+'</select></label>'+(String(x.source_category_url).startsWith('https://')?'<a class="link" href="'+esc(x.source_category_url)+'" target="_blank" rel="noopener noreferrer">View source category ↗</a>':'')+'</article>'}).join('')||'<div class="empty">No candidates in this filter.</div>'};$('reviewResults').addEventListener('change',e=>{const el=e.target;if(!el.matches('select[data-candidate-id]'))return;const id=el.getAttribute('data-candidate-id');if(!records.some(x=>x.candidate_id===id)||!allowed.includes(el.value))return;decisions[id]=el.value;localStorage.setItem(decisionsKey,JSON.stringify(decisions));renderReview()});$('reviewStatus').addEventListener('change',renderReview);$('reviewExportBtn').addEventListener('click',()=>{const cols=['candidate_id','retailer','advertised_product_name','category','advertised_price_usd','menu_status','decision','source_category_url'];const values=records.map(x=>cols.map(k=>k==='decision'?(decisions[x.candidate_id]||'pending'):String(x[k]??'')));const csv=[cols.join(','),...values.map(v=>v.map(z=>'"'+String(z).replace(/"/g,'""')+'"').join(','))].join('\\r\\n');download('mntrees-review-decisions.csv',csv,'text/csv');msg('Review decisions exported. No products have been published.')});renderReview()}catch(err){$('reviewCount').textContent='Review feed unavailable';$('reviewResults').innerHTML='<div class="empty">Candidate review data is not currently available.</div>'}}render();loadPublished()})();