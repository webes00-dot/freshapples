import catalogModel from '../catalog-model.js';

const normalize = value => String(value ?? '').normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const aliases = value => Array.isArray(value) ? value :
  String(value ?? '').split(/[,;|\n]/).map(item => item.trim()).filter(Boolean);
const present = value => typeof value === 'string' && value.trim() !== '';
const values = row => Object.fromEntries(Object.entries(row).filter(([, value]) => present(value)));

function httpUrl(value) {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? value : '';
  } catch {
    return '';
  }
}

function directoryIndex(rows, nameField) {
  const exact = new Map(rows.map(row => [normalize(row[nameField]), row]));
  const alternate = new Map();
  for (const row of rows) {
    for (const name of aliases(row.aliases)) {
      const key = normalize(name);
      if (alternate.has(key) && alternate.get(key) !== row) alternate.set(key, null);
      else alternate.set(key, row);
    }
  }
  return name => exact.get(normalize(name)) ?? alternate.get(normalize(name));
}

function urlIdentity(value) {
  if (!httpUrl(value)) return '';
  const url = new URL(value);
  return url.host.toLowerCase() + url.pathname.replace(/\/$/, '');
}

function listingKey(offer) {
  const url = urlIdentity(offer.url);
  if (!offer.retailer_id || !url) return '';
  const key = [offer.retailer_id, url, Number(offer.package_g) || 0];
  if (!/\/(products?\/|pdp\/)/i.test(url)) {
    key.push(normalize(offer.master_strain || offer.strain), normalize(offer.brand), normalize(offer.category));
  }
  return key.join('|');
}

function categoryOf(offer) {
  if (offer.category) return offer.category;
  const title = normalize(offer.product_name);
  if (/\b(gumm(?:y|ies)|edibles?|beverages?|chocolates?|tinctures?|topicals?)\b/.test(title)) return 'Other';
  if (/\b(pre ?rolls?|joints?|blunts?)\b/.test(title)) return 'Preroll';
  if (/\b(vapes?|cartridges?|carts?|disposables?)\b/.test(title)) return 'Vape';
  if (/\b(rosin|resin|concentrates?|hash|wax|shatter|badder)\b/.test(title)) return 'Concentrates';
  return /\b(flower|buds?)\b/.test(title) ? 'Flower' : '';
}

export function mergeCatalog(snapshot, {retailers, brands, strains, offers}) {
  const retailerRows = new Map();
  for (const row of retailers) {
    for (const key of [row.source_key, row.license_id].filter(Boolean)) retailerRows.set(key, row);
  }
  const retailerEntries = new Map(snapshot.retailers.map(row => [row.license_id || row.id, row]));
  const catalogRetailers = new Map();
  for (const [key, current] of retailerEntries) {
    const row = retailerRows.get(key);
    catalogRetailers.set(key, row ? {
      ...current,
      ...values({
        name: row.display_name, address: row.address, menu_url: httpUrl(row.menu_url),
        website_url: httpUrl(row.website_url), ownership_group: row.ownership_group,
      }),
      retailer_aliases: [...new Set([
        ...aliases(current.retailer_aliases), ...aliases(row.aliases),
        ...(row.display_name && current.name !== row.display_name ? [current.name] : []),
      ])],
    } : current);
  }
  for (const row of retailers) {
    const key = row.license_id || row.source_key;
    if (!catalogRetailers.has(key) && row.display_name) {
      catalogRetailers.set(key, {
        id: key, license_id: key, name: row.display_name, address: row.address || '',
        website_url: httpUrl(row.website_url), menu_url: httpUrl(row.menu_url),
        retailer_aliases: aliases(row.aliases), ownership_group: row.ownership_group || '',
      });
    }
  }

  const catalogBrands = new Map(snapshot.brands.map(brand => [normalize(brand.name), brand]));
  const brandTags = new Map((snapshot.business_tags?.brands || []).map(tag => [normalize(tag.name), tag]));
  const findLiveBrand = directoryIndex(brands, 'canonical_name');
  const legacyByBrand = new Map();
  const legacyAliases = new Map();
  for (const [key, legacy] of catalogBrands) {
    const legacyNames = [legacy.name, ...aliases(legacy.aliases)];
    const matches = new Set(legacyNames.map(findLiveBrand).filter(Boolean));
    const row = findLiveBrand(legacy.name) || (matches.size === 1 ? matches.values().next().value : null);
    if (!row) continue;
    const entries = legacyByBrand.get(row) || [];
    entries.push(legacy);
    legacyByBrand.set(row, entries);
    for (const name of legacyNames) {
      const alias = normalize(name);
      if (legacyAliases.has(alias) && legacyAliases.get(alias) !== row) legacyAliases.set(alias, null);
      else legacyAliases.set(alias, row);
    }
    if (key !== normalize(row.canonical_name)) catalogBrands.delete(key);
  }
  const findBrand = name => findLiveBrand(name) || legacyAliases.get(normalize(name));
  const inheritedTags = new Map();
  for (const [key, tag] of brandTags) {
    const row = findBrand(tag.name);
    if (!row || key === normalize(row.canonical_name)) continue;
    if (!inheritedTags.has(row)) inheritedTags.set(row, tag);
    brandTags.delete(key);
  }
  for (const row of brands) {
    const key = normalize(row.canonical_name);
    const legacy = legacyByBrand.get(row) || [];
    const existing = catalogBrands.get(key) || legacy[0];
    catalogBrands.set(key, {
      ...existing,
      ...values({
        name: row.canonical_name, url: httpUrl(row.website_url), summary: row.summary,
        logo_url: httpUrl(row.logo_url), about_url: httpUrl(row.about_url),
        cultivation_type: row.cultivation_type, research_status: row.research_status,
        ownership_group: row.ownership_group,
      }),
      aliases: [...new Set([...aliases(row.aliases), ...legacy.flatMap(entry => [entry.name, ...aliases(entry.aliases)])])]
        .filter(name => normalize(name) !== key && findBrand(name) === row),
    });
    const tag = {...(brandTags.get(key) || inheritedTags.get(row)), name: row.canonical_name, canonical_name: row.canonical_name};
    const verified = new Set(tag.verified_tags || []);
    for (const [field, label, status] of [
      ['tribal', 'Tribal', row.tribal_status],
      ['sea', 'SEA', row.sea_status],
      ['corporate', 'Corporate', row.corporate_tag],
    ]) {
      if (status !== 'Yes' && status !== 'No') continue;
      tag[field] = status;
      if (status === 'Yes') verified.add(label);
      else verified.delete(label);
    }
    brandTags.set(key, {...tag, verified_tags: [...verified]});
  }

  const findStrain = directoryIndex(strains, 'canonical_name');
  const genetics = new Map();
  for (const entry of snapshot.strain_genetics || []) {
    const key = normalize(entry.strain);
    if (!genetics.has(key)) genetics.set(key, []);
    genetics.get(key).push(entry);
  }
  const strainTypes = {...snapshot.strain_types};
  const references = {...snapshot.strain_profile_references};
  for (const row of strains) {
    const key = normalize(row.canonical_name);
    const entries = genetics.get(key) || [];
    const source = httpUrl(row.reference_url);
    const classification = row.classification || row.indica_sativa;
    if (classification) {
      for (const name of [row.canonical_name, ...aliases(row.aliases)]) strainTypes[name.toLowerCase()] = classification;
    }
    if (source) references[row.canonical_name] = {url: source, source: row.reference_name || new URL(source).hostname};
    const publicFields = values({
      classification, indica_sativa: classification, parent1: row.parent1, parent2: row.parent2,
      breeder: row.breeder, terpenes: row.terpenes, flowering_time: row.flowering_time,
      children: row.known_children, note: row.notes, source_url: source, source: row.reference_name,
    });
    if (Object.keys(publicFields).length) {
      genetics.set(key, [{...entries[0], strain: row.canonical_name, ...publicFields}, ...entries.slice(1)]);
    }
  }

  function enrich(offer) {
    const retailer = catalogRetailers.get(offer.retailer_id);
    const strain = findStrain(offer.master_strain || offer.strain);
    const brand = findBrand(offer.brand_family) || findBrand(offer.brand);
    return {
      ...offer,
      ...values({
        retailer: retailer?.name, address: retailer?.address,
        master_strain: strain?.canonical_name, strain_type: strain?.classification || strain?.indica_sativa,
        brand: brand?.canonical_name, brand_family: brand?.canonical_name,
      }),
    };
  }

  const catalog = snapshot.catalog.map(enrich);
  const productKeys = new Map();
  for (const [index, offer] of catalog.entries()) {
    const key = listingKey(offer);
    if (!key) continue;
    if (productKeys.has(key)) productKeys.set(key, null);
    else productKeys.set(key, index);
  }
  for (const row of offers) {
    const offer = JSON.parse(row.public_json);
    const product = enrich({
      id: offer.id, retailer_id: offer.store_id, retailer: offer.retailer,
      strain: offer.strain || offer.product_name, brand: offer.brand || '',
      product_name: offer.product_name, category: categoryOf(offer), package_g: offer.package_g,
      url: row.source_url, price: row.price_cents / 100, checked_at: row.observed_at,
      source_id: offer.source_id, source_method: offer.source_method, stock_status: 'not_verified',
      availability_status: 'listed', record_status: 'source_observed',
    });
    const key = listingKey(product);
    const index = productKeys.get(key);
    if (Number.isInteger(index)) {
      const current = catalog[index];
      if ((current.checked_at || "") <= product.checked_at) {
        catalog[index] = {...current, price: product.price, analytics_price: product.price, checked_at: product.checked_at};
      }
    } else {
      if (key && !productKeys.has(key)) productKeys.set(key, catalog.length);
      catalog.push(product);
    }
  }
  return {
    ...snapshot, catalog,
    retailers: [...catalogRetailers.values()], brands: [...catalogBrands.values()],
    business_tags: {...snapshot.business_tags, brands: [...brandTags.values()]},
    strain_genetics: [...genetics.values()].flat(), strain_types: strainTypes,
    strain_profile_references: references,
  };
}

export async function liveCatalog(request, env) {
  const url = new URL(request.url);
  const baselineUrl = new URL('/data/site-data.json', url);
  const response = await env.ASSETS.fetch(new Request(baselineUrl));
  if (!response.ok) return response;

  const queries = [
    "SELECT source_key, license_id, display_name, address, menu_url, website_url, aliases, ownership_group FROM retailers",
    "SELECT canonical_name, aliases, website_url, summary, about_url, cultivation_type, logo_url, research_status, ownership_group, tribal_status, sea_status, corporate_tag FROM brands",
    "SELECT canonical_name, aliases, classification, indica_sativa, parent1, parent2, breeder, terpenes, flowering_time, known_children, notes, reference_url, reference_name FROM strains",
    "SELECT observed_at, price_cents, source_url, public_json FROM scanner_offers ORDER BY observed_at DESC, offer_key",
  ];
  try {
    const [snapshot, results] = await Promise.all([
      response.json(),
      env.CATALOG_DB.batch(queries.map(sql => env.CATALOG_DB.prepare(sql))),
    ]);
    const [retailers, brands, strains, offers] = results.map(result => result.results);
    const data = mergeCatalog(snapshot, {retailers, brands, strains, offers});
    if (url.pathname === '/data/published-strains.json') {
      const listings = data.catalog.filter(offer => offer.retailer && offer.strain
        && Number.isFinite(Number(offer.price)) && Number(offer.price) > 0);
      const names = new Set();
      for (const group of catalogModel.groupOffers(listings)) {
        names.add(group.strain);
        for (const offer of group.offers) {
          if (offer.master_strain) names.add(offer.master_strain);
        }
      }
      return Response.json({strains: [...names].sort()}, {
        headers: {'Cache-Control': 'no-store', 'X-MNtrees-Catalog-Source': 'd1'},
      });
    }
    const routes = {
      '/data/catalog.json': data.catalog,
      '/data/brands.json': data.brands,
      '/data/retailer_locations.json': data.retailers,
    };
    return Response.json(routes[url.pathname] ?? data, {
      headers: {'Cache-Control': 'no-store', 'X-MNtrees-Catalog-Source': 'd1'},
    });
  } catch (error) {
    console.error('D1 catalog unavailable', error);
    return env.ASSETS.fetch(request);
  }
}
