const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const norm=s=>String(s||'').trim().toLowerCase();const grid=document.getElementById('brandGrid'),search=document.getElementById('brandSearch'),status=document.getElementById('status');let stores=[],offers=[],tags=[];const money=n=>'$'+n.toFixed(2);const kind = offer => MNtreesCatalog.typeOf(offer);
let expanded=false;function rankingData(){const groups=new Map();for(const o of offers){if(kind(o)!==document.getElementById('ranking-category').value)continue;const p=Number(o.analytics_price||o.price),g=Number(o.package_g);if(!(p>0&&p<=500&&g>0&&g<=112))continue;const store=storeFor(o);if(!store)continue;const keyGroup=groupKey(store);if(!groups.has(keyGroup))groups.set(keyGroup,{name:displayName(store),values:[],seen:new Set()});const x=groups.get(keyGroup),key=[o.strain||o.product_name,o.brand,o.category,g,p,o.product_variant].join('|').toLowerCase();if(x.seen.has(key))continue;x.seen.add(key);x.values.push(p/g)}return [...groups.values()].filter(x=>x.values.length>0).map(x=>({...x,avg:x.values.reduce((a,b)=>a+b,0)/x.values.length})).sort((a,b)=>a.avg-b.avg||a.name.localeCompare(b.name))}
function rankings(){const ranked=rankingData(),canExpand=ranked.length>5,showAll=canExpand&&expanded,midpoint=Math.ceil(ranked.length/2);const columns=showAll?[ranked.slice(0,midpoint),ranked.slice(midpoint).reverse()]:[ranked.slice(0,5),[...ranked].reverse().slice(0,5)];for(const [index,direction] of ['low','high'].entries()){const button=document.getElementById('ranking-'+direction+'-toggle'),list=document.getElementById('ranking-'+direction),ordered=columns[index];button.disabled=!canExpand;button.setAttribute('aria-expanded',String(showAll));button.title=showAll?'Collapse both ranking columns':'Show all qualifying retailers in two ranking columns';list.innerHTML=ordered.map((x,i)=>'<div class="ranking-item"><span class="ranking-number">'+(i+1)+'</span><span class="ranking-name"><a class="ranking-retailer-link" href="'+esc((()=>{const group=groups.find(g=>norm(g.name)===norm(x.name));return group?productLink(group.name,group.locations):'./?store='+encodeURIComponent(x.name)+'#compareTitle';})())+'" aria-label="View cataloged products at '+esc(x.name)+'">'+esc(x.name)+'</a>'+retailerGroupBadges(groups.find(g=>norm(g.name)===norm(x.name)))+'<small>'+x.values.length+' qualifying offers</small></span><span class="ranking-price">'+money(x.avg)+'/g</span></div>').join('')||'<p>No retailers meet the qualifying-offer minimum.</p>'}document.getElementById('ranking-note').textContent=ranked.length+' qualifying retailers. Mean advertised price per actual gram; Product sizes and grades are not standardized. Menu snapshots are not verified stock.'}
for(const d of ['low','high'])document.getElementById('ranking-'+d+'-toggle').onclick=()=>{expanded=!expanded;rankings()};document.getElementById('ranking-category').onchange=()=>{expanded=false;rankings()};

const retailerNames = [
  [/^mnloon(?:\s+[-—–]\s+|$)/i, 'MnLooN'],
  [/^mn roots(?:\s|$)/i, 'MN Roots'],
  [/^(?:green goods(?:\s+[-—–]\s+|$)|vireo health of minnesota$)/i, 'Green Goods'],
  [/^the flower shop mn(?:\s+[-—–]\s+|$)/i, 'The Flower Shop MN'],
  [/^legacy cannabis(?:\s|$)/i, 'Legacy Cannabis'],
  [/^green box cannabis(?:\s+[-—–]\s+|$)/i, 'Green Box Cannabis'],
  [/^dispo(?:\s+[-—–]\s+|$)/i, 'DISPO'],
  [/^rise dispensary(?:\s+[-—–]\s+|$)/i, 'RISE Dispensary'],
  [/^waabigwan mashkiki(?:\s+[-—–]\s+|$)/i, 'Waabigwan Mashkiki'],
  [/^nativecare(?:\s+[-—–]\s+|$)/i, 'NativeCare'],
  [/^mn thc co(?:\s+[-—–]\s+|$)/i, 'MN THC Co'],
  [/^black bear dispensary(?:\s+[·—–-]\s+|$)/i, 'Black Bear Dispensary'],
  [/^wildflower(?:\s+[-—–]\s+)?\s*(?:north loop|northeast(?: minneapolis)?)$/i, 'Wildflower'],
  [/^dankz(?:\s+[-—–]\s+st\. cloud)?$/i, 'DankZ'],
  [/^pot mamas(?:\s+[-—–]\s+|$)/i, 'Pot Mamas']
];

function displayName(store) {
  if (/^feelin['’]?\s*mn(?:\s*[—–-]\s*little canada)?$/i.test(String(store.name||""))) return "Feelin' MN";
  if (/^eagan canna$/i.test(store.name || '')) return 'MN Canna';
  if (/^MDCMB-L25-000002-|^SITE-GREEN-GOODS-/i.test(store.id || '')) return 'Green Goods';
  if (store.retailer_group) return store.retailer_group;
  const name = store.name.trim();
  const known = retailerNames.find(([pattern]) => pattern.test(name));
  return known?.[1] || name.split(/\s+[·—–-]\s+/)[0];
}

function groupKey(store) {
  if (/^feelin['’]?\s*mn(?:\s*[—–-]\s*little canada)?$/i.test(String(store.name||""))) return "feelin mn";
  if (/^eagan canna$/i.test(store.name || '')) return 'mn canna';
  if (/^MDCMB-L25-000002-|^SITE-GREEN-GOODS-/i.test(store.id || '')) return 'green goods';
  if (store.retailer_group) return norm(store.retailer_group);
  if (/^legit cannabis\b/i.test(store.name)) {
    // The metro/Duluth operator and similarly named businesses are distinct.
    return /^MEZZO-L24-000173-/i.test(store.id) ? 'legit cannabis' : 'legit-cannabis:' + norm(store.id);
  }
  const alias = retailerNames.find(([pattern]) => pattern.test(store.name.trim()));
  return norm(alias?.[1] || store.name);
}

function locationKey(store) {
  const group = groupKey(store);
  const address = norm(store.address);
  if (group === 'the flower shop mn' && /706 s kniss ave.*luverne/.test(address)) return '706-s-kniss-luverne';
  if (group === 'green box cannabis' && /lakeville/.test(address) && /^16350\s/.test(address)) return '16350-lakeville';
  if (group === 'wildflower' && /212 n 2nd st/.test(address)) return '212-n-2nd';
  if (group === 'wildflower' && /^326 .*central/.test(address)) return '326-central';
  if (group === 'dankz' && /^3105 1st st/.test(address)) return '3105-1st';
  if (group === 'green goods') {
    const city = address.match(/\b(blaine|bloomington|burnsville|hermantown|minneapolis|moorhead|rochester|woodbury)\b/);
    if (city) return city[1];
  }
  return address.replace(/[^a-z0-9]/g, '') || norm(store.id);
}

let groups = [];
const storesById = new Map();
const storesByName = new Map();
const offersByStore = new Map();

function storeFor(offer) {
  const byId = storesById.get(norm(offer.retailer_id));
  if (byId) return byId;
  const byName = storesByName.get(norm(offer.retailer));
  return byName?.length === 1 ? byName[0] : null;
}

function prepareDirectory() {
  const grouped = new Map();
  for (const store of stores) {
    if (store.id) storesById.set(norm(store.id), store);
    for (const name of new Set([store.name, store.legal_name, ...(store.retailer_aliases || [])].map(norm))) {
      if (!name) continue;
      if (!storesByName.has(name)) storesByName.set(name, []);
      storesByName.get(name).push(store);
    }

    const key = groupKey(store);
    if (!grouped.has(key)) grouped.set(key, {name: displayName(store), locations: new Map()});
    const locations = grouped.get(key).locations;
    const addressKey = locationKey(store);
    if (!locations.has(addressKey)) locations.set(addressKey, {primary: store, sourceRecords: []});
    const location = locations.get(addressKey);
    location.sourceRecords.push(store);
    if (/^green goods/i.test(store.name)) location.primary = store;
  }
  for (const offer of offers) {
    const store = storeFor(offer);
    if (!store) continue;
    if (!offersByStore.has(store)) offersByStore.set(store, []);
    offersByStore.get(store).push(offer);
  }
  // The public directory is a catalog-backed retailer directory, not a list
  // of every licensed or researched storefront. Keep zero-offer records in
  // memory, so a later successful scan can make them visible automatically.
  groups = [...grouped.values()].map(group => {
    const allLocations = [...group.locations.values()];
    const locations = allLocations.filter(location => productsFor(location).length > 0);
    return {
      name: group.name,
      // Ownership applies to the whole operator, including an unlisted branch.
      corporate: allLocations.some(location => location.sourceRecords.some(store => {
        const tag = tags.find(entry => norm(entry.id) === norm(store.id));
        return tag?.corporate === 'Yes' || (tag?.verified_tags || []).includes('Corporate');
      })),
      sea: allLocations.length > 0 && allLocations.every(location => location.sourceRecords.some(store => {
        const tag = tags.find(entry => norm(entry.id) === norm(store.id));
        return tag?.sea === 'Yes' || (tag?.verified_tags || []).includes('SEA');
      })),
      tribal: allLocations.some(location => location.sourceRecords.some(store => {
        const tag = tags.find(entry => norm(entry.id) === norm(store.id));
        return tag?.tribal === 'Yes' || (tag?.verified_tags || []).includes('Tribal');
      })),
      locations: locations.sort((a, b) =>
        Number(b.primary.opening_status === 'open') - Number(a.primary.opening_status === 'open') ||
        norm(a.primary.address).localeCompare(norm(b.primary.address)))
    };
  }).filter(group => group.locations.length > 0)
    .sort((a, b) => a.name.localeCompare(b.name));
}

function productsFor(location) {
  return location.sourceRecords.flatMap(store => offersByStore.get(store) || []);
}

function productLink(groupName, locations) {
  const records = locations.flatMap(location => location.sourceRecords);
  const products = locations.flatMap(productsFor);
  if (!products.length) return '';
  const params = new URLSearchParams({retailer: groupName});
  for (const id of new Set([...records.map(store => store.id), ...products.map(offer => offer.retailer_id)])) {
    if (id) params.append('storeId', id);
  }
  for (const name of new Set([...records.flatMap(store => [store.name, ...(store.retailer_aliases || [])]), ...products.map(offer => offer.retailer)])) {
    if (name) params.append('store', name);
  }
  return './?' + params + '#compareTitle';
}

function link(href, label, external = false) {
  if (!href) return '';
  return '<a href="' + esc(href) + '"' + (external ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' + esc(label) + '</a>';
}

// Ownership is attributed at the retailer/operator group level. One verified
// Corporate location makes the whole group Corporate, irrespective of how many
// site-specific flags have been completed in Retailer Master.
function isCorporateGroup(group) {
  return group.corporate === true;
}

function retailerGroupBadges(group) {
  if (!group) return '';
  const labels = [group.sea ? 'SEA' : '', group.corporate ? 'Corporate' : '', group.tribal ? 'Tribal' : ''].filter(Boolean);
  return labels.map(label => '<span class="business-tag ' + (label === 'SEA' ? 'sea-tag' : 'ownership-tag ' + (label === 'Tribal' ? 'tribal-tag' : 'corporate-tag')) + '" title="Retailer classification">' + esc(label) + '</span>').join('');
}

function renderLocation(groupName, location, groupSea = false) {
  const {primary, sourceRecords} = location;
  // Spreadsheet classification is keyed to license/site ID; a shared legal
  // name alone is never evidence that another branch has the same flags.
  const matchingTags = sourceRecords.map(store => tags.find(entry => norm(entry.id) === norm(store.id))).filter(Boolean);
  const verified = new Set(matchingTags.flatMap(entry => [...(entry.verified_tags || []), ...(entry.sea === 'Yes' ? ['SEA'] : [])]));
  // Ownership badges appear only at retailer/operator level, never per location.
  verified.delete('Tribal');
  verified.delete('Corporate');
  // Do not repeat the retailer-level SEA badge within a location on the same card.
  if (groupSea) verified.delete('SEA');
  const badges = [...verified].map(tag => {
    const colorClass = tag === 'SEA' ? ' sea-tag' : (/^(Tribal|Corporate)$/.test(tag) ? ' ownership-tag' : '');
    return '<span class="business-tag' + colorClass + '">' + esc(tag) + '</span>';
  }).join('');
  const products = productsFor(location);
  const contact = field => primary[field] || sourceRecords.find(store => store[field])?.[field];
  const map = contact('google_business_url') || 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(primary.map_address || primary.address);
  const openingStatus = {open: 'Open', coming_soon: 'Coming soon'}[primary.opening_status];
  return '<div class="retailer-location">' +
    (primary.location_label ? '<strong>' + esc(primary.location_label) + '</strong>' : '') +
    (openingStatus ? '<p>' + openingStatus + '</p>' : '') +
    (badges ? '<div class="business-tags">' + badges + '</div>' : '') +
    '<p>' + esc(primary.address) + '</p><p>' + products.length + ' catalog offers</p>' +
    '<div class="links">' +
    link(contact('website_url'), 'Website', true) + link(contact('menu_url'), 'Menu', true) +
    link(map, 'Map', true) + link(productLink(groupName, [location]), 'View strains') +
    '</div></div>';
}

function render() {
  const term = norm(search.value);
  const visible = groups.filter(group => !term || norm(group.name).includes(term) || (term === 'viero' && norm(group.name).includes('vireo')) ||
    group.locations.some(location => location.sourceRecords.some(store => [store.name, store.legal_name, store.location_label, store.address, ...(store.retailer_aliases || [])].some(value => norm(value).includes(term)))));
  status.textContent = visible.length + ' retailer groups across ' +
    visible.reduce((total, group) => total + group.locations.length, 0) + ' locations' + (term ? ' matching search' : '') + '.';
  grid.innerHTML = visible.map(group => {
    const locations = group.locations.map(location => renderLocation(group.name, location, group.sea)).join('');
    const directory = group.locations.length > 1
      ? '<div class="links">' + link(productLink(group.name, group.locations), 'View strains') + '</div>' +
        '<details><summary>View ' + group.locations.length + ' locations</summary>' + locations + '</details>'
      : locations;
    const groupBadges = retailerGroupBadges(group);
    const ownership = groupBadges ? '<div class="business-tags retailer-group-tags">' + groupBadges + '</div>' : '';
    return '<article class="brand-card"><div class="retailer-group-heading"><h2>' +
      esc(group.name) + '</h2>' + ownership + '</div>' + directory + '</article>';
  }).join('');
}

search.oninput = render;
fetch('data/site-data.json', {cache: 'no-store'}).then(async response => {
  if (!response.ok) throw Error('Unified site data unavailable');
  const data = await response.json();
  if (data.schema_version !== 1 || !Array.isArray(data.catalog) || !Array.isArray(data.retailers)) {
    throw Error('Invalid unified site data');
  }
  return [data.retailers, data.catalog, data.business_tags];
}).then(([locations, catalog, businessTags]) => {
  stores = locations;
  offers = catalog;
  tags = businessTags.retailers || [];
  prepareDirectory();
  render();
  rankings();
}).catch(error => {
  status.textContent = 'Retailer directory temporarily unavailable.';
  console.error(error);
});
