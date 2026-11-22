const grid = document.getElementById('brandGrid');
const search = document.getElementById('brandSearch');
const status = document.getElementById('status');
const sheet = 'https://docs.google.com/spreadsheets/d/1sTqBuJ2eFHwhLlYHIlXhh6HqgMhcBmVb7o70pvwRtV8/edit?gid=1972464305';
const norm = s => String(s || '').normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
const esc = s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let brands = [];
let catalogBrandKeys = new Set();
const tagData = new Map();
const canonicalBrand = MNtreesCatalog.canonicalBrand;
const brandKey = name => norm(canonicalBrand(name));
const isOwnershipTag = label => label === 'Tribal' || label === 'Corporate';
const cultivationByBrand = new Map();

function cultivationBadge(name) {
 const label = cultivationByBrand.get(brandKey(name));
 return label ? '<span class="business-tag cultivation-tag" data-cultivation="' + esc(label) + '" title="Cultivation type">' + esc(label) + '</span>' : '';
}

function businessBadges(name, ownershipOnly = false) {
 const labels = tagData.get(brandKey(name)) || [];
 return labels.filter(label => !ownershipOnly || isOwnershipTag(label)).map(label =>
  '<span class="business-tag' + (isOwnershipTag(label) ? ' ownership-tag ' + (label === 'Tribal' ? 'tribal-tag' : 'corporate-tag') : (label === 'SEA' ? ' sea-tag' : '')) + '" title="Business classification">' + esc(label) + '</span>'
 ).join('');
}

function tagsFor(brand) {
 const tags = cultivationBadge(brand.name) + businessBadges(brand.name);
 return tags ? '<div class="business-tags">' + tags + '</div>' : '';
}

function renderDirectory() {
 const query = search.value.trim().toLowerCase();
 const items = brands.filter(brand => [brand.name, ...(brand.aliases || [])].some(name => catalogBrandKeys.has(brandKey(name))) && brand.name.toLowerCase().includes(query));
 grid.innerHTML = items.map(brand =>
  '<article class="brand-card">' + (brand.logo_url && /^https:\/\//i.test(brand.logo_url) ? '<img class="brand-watermark" src="' + esc(brand.logo_url) + '" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true">' : '') + '<div class="brand-card-content"><h2>' + esc(brand.name) + '</h2>' + tagsFor(brand) +
  '<p>' + esc(brand.summary || 'Company description pending verification.') + '</p>' + '<div class="links">' +
  (brand.url ? '<a href="' + esc(brand.url) + '" target="_blank" rel="noopener noreferrer">Official website ↗</a>' : '') +
  (brand.strain_library_url ? '<a href="' + esc(brand.strain_library_url) + '" target="_blank" rel="noopener noreferrer">Strain Library ↗</a>' : '') +
  (!brand.url && brand.about_url && /^https:\/\//i.test(brand.about_url) ? '<a href="' + esc(brand.about_url) + '" target="_blank" rel="noopener noreferrer">Listing source ↗</a>' : '') +
  '<a href="./?brand=' + encodeURIComponent(brand.name) + '">View products</a></div></div></article>'
 ).join('');
 status.textContent = items.length + ' brands' + (query ? ' matching search' : '') + '.';
}

search.addEventListener('input', renderDirectory);
const siteData = fetch('data/site-data.json', {cache: 'no-store'}).then(async response => {
 if (!response.ok) throw Error('Unified site data unavailable');
 const data = await response.json();
 if (data.schema_version !== 1 || !Array.isArray(data.catalog) || !Array.isArray(data.brands)) throw Error('Invalid unified site data');
 return data;
});
const brandDirectory = siteData.then(data => data.brands).then(data => {
 const aliases = new Map([['auroracannabisllc','Aurora'],['auroracannabis','Aurora'],['auroras','Aurora'],['danbey','Dabney\'s Cannabis Co.'],['danbeys','Dabney\'s Cannabis Co.'],['dabneys','Dabney\'s Cannabis Co.'],['valhalla','Valhalla Cannabis'],['vahalla','Valhalla Cannabis'],['valhallacannabisco','Valhalla Cannabis'],['valhallacannabiscompany','Valhalla Cannabis'],['valhallaconfections','Valhalla Cannabis'],['popcorn','Zips'],['feelinmn',"Feelin' MN"],['feelnmn',"Feelin' MN"]]);
 const keyOf = name => norm(name).replace(/[^a-z0-9]/g, '');
 const merged = new Map();
 for (const entry of data) { const canonical = aliases.get(keyOf(entry.name)) || entry.name; const key = keyOf(canonical); const prior = merged.get(key); if (!prior) merged.set(key, {...entry,name:canonical}); else merged.set(key,{...entry,...prior,name:canonical,aliases:[...new Set([...(prior.aliases||[]),...(entry.aliases||[]),entry.name])],url:prior.url||entry.url,summary:prior.summary||entry.summary}); }
 brands = [...merged.values()].sort((a,b)=>a.name.localeCompare(b.name));
 for (const brand of brands) {
  if (brand.cultivation_type !== 'Indoor' && brand.cultivation_type !== 'Outdoor') continue;
  for (const name of [brand.name, ...(brand.aliases || [])]) {
   cultivationByBrand.set(brandKey(name), brand.cultivation_type);
  }
 }
});

const businessTags = siteData.then(data => data.business_tags || {brands: []})
 .then(tags => {
  for (const entry of tags.brands || []) {
   if (!Array.isArray(entry.verified_tags)) continue;
   const key = brandKey(entry.name);
   tagData.set(key, [...new Set([...(tagData.get(key) || []), ...entry.verified_tags])]);
  }
 })
 .catch(() => {});

const publishedBrandNames = siteData.then(data => data.catalog).then(data => {
 const published = Array.isArray(data) ? data : Array.isArray(data.listings) ? data.listings : [];
 const valid = published.filter(offer => Number(offer.price) > 0);
 catalogBrandKeys = new Set(valid.flatMap(offer =>
  [offer.brand, offer.brand_family].filter(Boolean).map(brandKey)));
});

Promise.all([brandDirectory, businessTags, publishedBrandNames]).then(() => {
 renderDirectory();
}).catch(() => {
 status.textContent = 'Brand directory is temporarily unavailable. You can review the master spreadsheet.';
 grid.innerHTML = '<a href="' + sheet + '">Open Brand Master</a>';
});

/* Price comparisons: published, positive-priced, known-weight offers only. */
(function(){
 const select = document.getElementById('ranking-category');
 const note = document.getElementById('ranking-note');
 const previewSize = 5;
 let expanded = false;
 const panels = ['low', 'high'].map(direction => ({
  button: document.getElementById('ranking-' + direction + '-toggle'),
  list: document.getElementById('ranking-' + direction)
 }));
 const money = n => '$' + n.toFixed(2);
 const classify=o=>{const c=String(o.category||'').toLowerCase();if(/edible|gummy|vape|cartridge|disposable|tincture|beverage/.test(c))return null;if(/pre.?roll|joint|blunt/.test(c))return 'Preroll';if(/flower|bud/.test(c))return 'Flower';if(/concentrate|extract|rosin|resin|wax|shatter|badder|budder|hash|diamonds|crumble/.test(c))return 'Concentrates';return null};
 let catalog = [];
 let ranked = [];
 let minimumOffers = 0;

 function drawRankings() {
  const max = Math.max(1, ...ranked.map(brand => brand.avg));
  const canExpand = ranked.length > previewSize;
  const showAll = canExpand && expanded;
  const midpoint = Math.ceil(ranked.length / 2);
  // Expanded columns partition the complete list without repeating brands.
  // Collapsed columns retain the original five best and five most expensive.
  const ordered = showAll
   ? [ranked.slice(0, midpoint), ranked.slice(midpoint).reverse()]
   : [ranked.slice(0, previewSize), [...ranked].reverse().slice(0, previewSize)];
  panels.forEach((panel, index) => {
   panel.button.disabled = !canExpand;
   panel.button.setAttribute('aria-expanded', String(showAll));
   panel.button.title = showAll ? 'Collapse both ranking columns' : 'Show all qualifying brands in two ranking columns';
   const items = ordered[index];
   panel.list.innerHTML = items.length ? items.map((brand, rank) => {
    const width = Math.max(3, Math.min(100, brand.avg / max * 100)).toFixed(1);
    return `<div class="ranking-item">
     <span class="ranking-number">${rank + 1}</span>
     <span class="ranking-name"><a class="ranking-brand-link" href="./?brand=${encodeURIComponent(brand.name)}#compareTitle" aria-label="View cataloged products for ${esc(brand.name)}">${esc(brand.name)}</a>${cultivationBadge(brand.name)}${businessBadges(brand.name)}<small>${brand.count} qualifying ${brand.count === 1 ? 'offer' : 'offers'}</small></span>
     <span class="ranking-price">${money(brand.avg)}/g</span>
     <div class="ranking-track"><span class="ranking-fill" style="width:${width}%"></span></div>
    </div>`;
   }).join('') : `<p class="brands-note">No brands have enough valid priced offers for this category yet.</p>`;
  });
 }

 function render() {
  const type = select.value;
  expanded = false;
  minimumOffers = type === 'Concentrates' ? 0 : 10;
  const groups = new Map();
  for (const offer of catalog) {
   if (classify(offer) !== type) continue;
   const brand = canonicalBrand(offer.brand);
   const price = Number(offer.analytics_price || offer.price);
   const grams = Number(offer.package_g);
   if (!brand || /^(unknown|unconfirmed|brand not confirmed|n\/a)$/i.test(brand) ||
       !Number.isFinite(price) || price <= 0 || price > 500 ||
       !Number.isFinite(grams) || grams <= 0 || grams > 112) continue;
   const key = norm(brand);
   if (!groups.has(key)) groups.set(key, {name: brand, values: [], seen: new Set()});
   const group = groups.get(key);
   const unique = [offer.retailer_id || offer.retailer || '', offer.strain || offer.product_name || '',
    offer.category || '', grams, price].join('|').toLowerCase();
   if (group.seen.has(unique)) continue;
   group.seen.add(unique);
   group.values.push(price / grams);
  }
  ranked = [...groups.values()]
   .filter(group => group.values.length > 0 && group.values.length >= minimumOffers)
   .map(group => ({
    name: group.name,
    count: group.values.length,
    avg: group.values.reduce((sum, value) => sum + value, 0) / group.values.length
   }))
   .sort((a, b) => a.avg - b.avg || a.name.localeCompare(b.name));
  drawRankings();
  note.textContent = ranked.length + ' qualifying brands for '+type.toLowerCase()+'. '+(minimumOffers ? 'Minimum '+minimumOffers+' distinct qualifying offers per brand. ' : '')+'Rankings are mean advertised $/g (not a median or cheapest offer). One product offered in several stores may contribute several observations. Price, potency, grade and package-size differences are not controlled; these are menu snapshots, not verified stock.';
 }

 panels.forEach(panel => {
  panel.button.addEventListener('click', () => {
   expanded = !expanded;
   drawRankings();
  });
 });
 const pricingCatalog = siteData.then(data => data.catalog);
 Promise.all([pricingCatalog, brandDirectory.catch(() => {}), businessTags]).then(([data]) => {
  catalog = Array.isArray(data) ? data : Array.isArray(data.listings) ? data.listings : [];
  render();
  select.addEventListener('change', render);
 }).catch(() => {
  panels.forEach(panel => {
   panel.list.textContent = 'Pricing data temporarily unavailable.';
  });
  note.textContent = 'Brand rankings will return when the published catalog is available.';
 });
})();
