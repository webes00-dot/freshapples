(() => {
'use strict';
const $=id=>document.getElementById(id);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stateBounds=[[43.45,-97.35],[49.45,-89.20]];
const pins=new Map();
let stores=[],selected=null,map=null,markers=null;let businessTags=[];let relatedGreenGoodsTags=new Map();
const normTag=s=>String(s||'').trim().toLowerCase();
function badges(store){const direct=businessTags.find(x=>normTag(x.id)===normTag(store.id))||{};const linked=relatedGreenGoodsTags.get(store.id)||[];const records=[direct,...linked];const labels=[direct.origin==='MN Local'?'MN Local':'',direct.sea==='Yes'?'SEA':'',records.some(t=>t.tribal==='Yes')?'Tribal':'',records.some(t=>t.corporate==='Yes')?'Corporate':''].filter(Boolean);return labels.length?'<span class="business-tags">'+labels.map(x=>'<span class="business-tag' + (x === 'SEA' ? ' sea-tag' : (/^(Tribal|Corporate)$/.test(x) ? ' ownership-tag ' + (x === 'Tribal' ? 'tribal-tag' : 'corporate-tag') : '')) + '">'+safe(x)+'</span>').join('')+'</span>':'';
}
const pendingGeocodes=new Map();
let embeddedMap=null;
function showEmbeddedAddress(store){
 if(!embeddedMap){embeddedMap=document.createElement('iframe');embeddedMap.title='Selected retailer street-address map';embeddedMap.loading='eager';embeddedMap.referrerPolicy='no-referrer-when-downgrade';embeddedMap.style.cssText='width:100%;height:100%;border:0;position:absolute;inset:0;z-index:600';}
 const container=$('store-map');if(getComputedStyle(container).position==='static')container.style.position='relative';
 embeddedMap.src='https://maps.google.com/maps?q='+encodeURIComponent(placeQuery(store)+', USA')+'&z=16&output=embed';
 container.appendChild(embeddedMap);
}
function showOverviewMap(){if(embeddedMap)embeddedMap.remove();if(map){map.closePopup();setTimeout(()=>map.invalidateSize(),50)}}
const products=s=>s==='confirmed_product_menu';
const hasMenu=s=>products(s)||['confirmed_store_menu','menu_link_prior_audit','official_menu_page_product_extraction_pending','spreadsheet_active_url_unverified','third_party_priced_menu_observed'].includes(s);
const menuLabel=s=>products(s)?'Priced menu identified':hasMenu(s)?'Menu / shop listed':'Website / verification pending';
const placeQuery=s=>s.map_address||s.address;
const normalizedAddress=s=>String(s||'').toLowerCase().replace(/\b(street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?)\b/g,x=>({street:'st',st:'st',avenue:'ave',ave:'ave',road:'rd',rd:'rd',drive:'dr',dr:'dr'}[x.replace('.','')]||x.replace('.',''))).replace(/[^a-z0-9]/g,'');
const validCoordinate=s=>['address_verified','rooftop_verified','census_address_range_interpolated'].includes(s.coordinate_accuracy)&&normalizedAddress(s.coordinate_for_address)===normalizedAddress(placeQuery(s));
const businessLink=s=>'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(placeQuery(s)+', USA');
const addressLink=s=>'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(placeQuery(s)+', USA');
const directionsLink=s=>'https://www.google.com/maps/dir/?api=1&destination='+encodeURIComponent(placeQuery(s)+', USA');
function actions(links){
 const el=$('map-actions');el.replaceChildren();
 for(const [label,url,secondary] of links){
  const a=document.createElement('a');a.textContent=label;a.href=url;a.target='_blank';a.rel='noopener noreferrer';
  if(secondary)a.className='secondary-action';el.appendChild(a);
 }
}
async function resolveInMap(store){
 if(pins.has(store.id))return pins.get(store.id);
 if(pendingGeocodes.has(store.id))return pendingGeocodes.get(store.id);
 const task=(async()=>{
  const url='https://geocode-api.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?'+new URLSearchParams({SingleLine:placeQuery(store)+', USA',f:'json',outFields:'Addr_type,Match_addr',maxLocations:'1'});
  const response=await fetch(url);
  if(!response.ok)throw Error('Address lookup unavailable');
  const data=await response.json();const match=(data.candidates||[])[0];
  const kind=match?.attributes?.Addr_type;
  if(!match||match.score<90||!['PointAddress','Subaddress','StreetAddress'].includes(kind))throw Error('Street-level match unavailable');
  const matched=String(match?.attributes?.Match_addr||'');const streetNumber=String(placeQuery(store)).match(/^\s*\d+/)?.[0];if(!streetNumber||!new RegExp('^\\s*'+streetNumber+'\\b').test(matched))throw Error('Street number mismatch');
  const lat=Number(match.location.y),lng=Number(match.location.x);
  if(!(lat>43&&lat<50&&lng> -98&&lng< -89))throw Error('Location outside Minnesota');
  const marker=L.marker([lat,lng],{title:store.name});
  marker.bindPopup(popupContent(store));
  marker.on('click',()=>select(store,false));
  pins.set(store.id,marker);refreshPins();return marker;
 })().finally(()=>pendingGeocodes.delete(store.id));
 pendingGeocodes.set(store.id,task);return task;
}
function popupContent(store){return '<div class="retailer-popup"><strong>'+safe(store.name)+'</strong><div>'+safe(placeQuery(store))+'</div><div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap"><a href="'+safe(businessLink(store))+'" target="_blank" rel="noopener noreferrer">Google Maps</a><a href="'+safe(directionsLink(store))+'" target="_blank" rel="noopener noreferrer">Directions</a>'+(store.menu_url&&/^https:\/\//.test(store.menu_url)?'<a href="'+safe(store.menu_url)+'" target="_blank" rel="noopener noreferrer">Store menu</a>':'')+'</div>'+(store.coordinate_accuracy==='census_address_range_interpolated'?'<small>Approximate street-range location from US Census; not a storefront rooftop</small>':'')+'</div>'}
async function select(store,focus=true){
 selected=store;
 $('selected-name').textContent=store.name;
 $('selected-address').textContent=placeQuery(store)+', USA';
 actions([
  ['Open Google Maps',businessLink(store),false],
  ['Directions',directionsLink(store),true],
  ...(store.menu_url&&/^https:\/\//.test(store.menu_url)?[['Store menu',store.menu_url,true]]:[]),
  ['Report address / website correction','feedback.html?retailer='+encodeURIComponent(store.name)+'&license='+encodeURIComponent(store.id),true]
 ]);
 history.replaceState(null,'','#'+encodeURIComponent(store.id));
 showOverviewMap();
 renderList();
 let pin=pins.get(store.id);
 if(!pin){
  $('selected-address').textContent=placeQuery(store)+', USA · Checking street-address position…';
  try{pin=await resolveInMap(store)}catch(e){
   if(selected===store)$('selected-address').textContent=placeQuery(store)+', USA · Exact map position not verified; use Google Maps link';
   return;
  }
 }
 if(selected!==store)return;
 $('selected-address').textContent=placeQuery(store)+', USA';
 if(focus)map.setView(pin.getLatLng(),16,{animate:false});
 L.popup({autoPan:focus,closeButton:true,maxWidth:340}).setLatLng(pin.getLatLng()).setContent(popupContent(store)).openOn(map);
}

function overview(resetHash=false){
 showOverviewMap();
 selected=null;$('selected-name').textContent='Minnesota retailers';
 $('selected-address').textContent='All mapped store areas · click a pin or retailer to explore';
 actions([]);
 if(map)map.fitBounds(stateBounds,{padding:[16,16],animate:false});
 if(resetHash)history.replaceState(null,'',location.pathname+location.search);
 renderList();
}
function filtered(){
 const q=$('map-search').value.trim().toLocaleLowerCase(),kind=$('map-filter').value;
 return stores.filter(s=>(kind==='all'||(kind==='products'?products(s.status):hasMenu(s.status)))
 &&[s.name,s.legal_name,s.address,s.id,...(s.retailer_aliases||[])].some(v=>String(v||'').toLocaleLowerCase().includes(q)));
}
function renderList(){
 const list=$('map-results');list.replaceChildren();const visible=filtered();
 $('map-count').textContent=visible.length+' of '+stores.length+' retailers';
 if(!visible.length){list.innerHTML='<p class="map-empty">No matching retailers. Clear the search or filter.</p>';return}
 for(const s of visible){
  const b=document.createElement('button');b.type='button';b.className='map-place'+(selected&&selected.id===s.id?' selected':'');
  b.setAttribute('role','option');b.setAttribute('aria-selected',String(Boolean(selected&&selected.id===s.id)));
  b.innerHTML='<strong>'+safe(s.name)+'</strong><small>'+safe(placeQuery(s))+'</small>'+badges(s)+'<span class="map-status">'+safe(menuLabel(s.status))+'</span>';
  b.addEventListener('click',()=>select(s));list.appendChild(b);
 }
}
function drawPins(){
 markers=L.markerClusterGroup?L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:35,spiderfyOnMaxZoom:true}):L.layerGroup();
 const show=new Set(filtered().map(x=>x.id));
 for(const [id,marker] of pins)if(show.has(id))markers.addLayer(marker);
 markers.addTo(map);
}
function refreshPins(){
 if(!map)return;
 if(markers)map.removeLayer(markers);
 drawPins();
}
async function init(){
 $('map-reset').addEventListener('click',()=>overview(true));
 $('map-search').addEventListener('input',()=>{renderList();refreshPins()});
 $('map-filter').addEventListener('change',()=>{renderList();refreshPins()});
 try{
  try{const tagsResponse=await fetch('./data/business_tags.json',{cache:'no-store'});if(tagsResponse.ok){const tagJson=await tagsResponse.json();businessTags=tagJson.retailers||[]}}catch{}
  const response=await fetch('./data/retailer_locations.json',{cache:'no-store'});
  if(!response.ok)throw Error('Directory request failed');
  const data=await response.json();if(!Array.isArray(data))throw Error('Invalid directory');
  // Tie the official storefront and Vireo license rows by the same city.
  // Preserve location-specific flags exactly as marked in Retailer Master.
  const greenCity=s=>String(s.address||'').toLowerCase().match(/\b(blaine|bloomington|burnsville|hermantown|minneapolis|moorhead|rochester|woodbury)\b/)?.[1];
  const vireoByCity=new Map(data.filter(s=>/^MDCMB-L25-000002-/i.test(s.id)).map(s=>[greenCity(s),s.id]));
  relatedGreenGoodsTags=new Map(data.filter(s=>/^SITE-GREEN-GOODS-/i.test(s.id)).map(s=>[
    s.id,businessTags.filter(t=>t.id===vireoByCity.get(greenCity(s)))
  ]));
  // Official Green Goods storefront rows are displayed once per location.
  // Vireo license entries refer to those same eight shops, not eight extra stores.
  stores=data.filter(s=>s.id&&s.name&&s.address&&!/^MDCMB-L25-000002-/i.test(s.id)).map(s=>s.id==='MICRO-L25-000490-01-AUR'?{...s,name:'Cali Cannabis',legal_name:'ADHI Enterprise LLC',menu_url:'https://calimn.com/shop'}:/^SITE-GREEN-GOODS-/i.test(s.id)?{...s,retailer_aliases:['Vireo Health of Minnesota','Viero','Green Goods (Vireo)']}:s).sort((a,b)=>a.name.localeCompare(b.name)||a.address.localeCompare(b.address));
  if(!window.L)throw Error('Map library unavailable');
  map=L.map('store-map',{scrollWheelZoom:true,dragging:true,touchZoom:true,doubleClickZoom:true,boxZoom:true,keyboard:true,zoomControl:true,preferCanvas:true});
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',maxZoom:18}).addTo(map);
  for(const s of stores){
   const lat=Number(s.lat),lng=Number(s.lng);
   // Do not place store markers at ZIP centroids or unresolved coordinates.
   if(!validCoordinate(s))continue;
   if(!Number.isFinite(lat)||!Number.isFinite(lng)||lat<43||lat>50||lng< -98||lng> -89)continue;
   const pin=L.marker([lat,lng],{title:s.name});
   pin.bindPopup(popupContent(s),{autoPan:false,maxWidth:340});
   pin.on('click',()=>select(s,false));
   pins.set(s.id,pin);
  }
  drawPins();
  // Resolve missing address-level markers progressively; never fall back to ZIP centroids.
  const unresolved=stores.filter(s=>!pins.has(s.id));
  (async()=>{for(const store of unresolved){
   try{await resolveInMap(store)}catch{}
   await new Promise(resolve=>setTimeout(resolve,350));
  }})();
  const deepId=decodeURIComponent(location.hash.slice(1));
  const chosen=deepId&&stores.find(x=>x.id===deepId);
  if(chosen)select(chosen);else overview();
 }catch(err){
  $('map-count').textContent='Retailer map unavailable';
  $('map-results').textContent='The retailer map could not load. Reload to retry.';
  $('selected-address').textContent=String(err.message||'Unable to load the map.');
 }
}
init();
})();