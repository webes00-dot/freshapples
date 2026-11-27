import titleRules from './menu-title-rules.json' with { type: 'json' };

const normalize = value => String(value ?? '').normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

const leadingForm = /^(?:(?:\d+\s*\/\s*\d+|\d*\.?\d+)\s*g(?:rams?)?\s+)?(?:(?:thc\s+)?(?:vape cartridge|vape pen|disposable)(?:\s+with battery)?|(?:cured|live|hash)\s+(?:resin|rosin)|select grind)\b/i;
const trailingForm = /\s+(?:(?:\d+\s*\/\s*\d+|\d*\.?\d+)\s*g(?:m|rams?)?(?:\s+.*)?|(?:(?:cured|live|hash)\s+)?(?:resin|rosin|distillate)(?:\s+(?:\d*\.?\d+\s*g\b.*|all[- ]in[- ]one\b.*|vape\b.*|disposable\b.*))?|(?:flower|vape(?:\s+cartridge)?|disposable|pre[- ]?rolls?|concentrate))$/i;
const menuDetail = /^(?:(?:deli(?:[- ]style)?|select grind|pre[- ]?packaged|flower|concentrates?|(?:cured |live |hash )?(?:rosin|resin)|distillate|vapes?|vape cartridges?|disposable(?: vape)?|pre[- ]?rolls?)|(?:indica|sativa|hybrid)(?:\s+(?:dominant|vibey energy))?|(?:\d+\s*\/\s*\d+|\d*\.?\d+)\s*g(?:m|rams?)?(?:\s*\/\s*\d+\s*(?:pk|packs?|ct)(?:\s+.*)?)?|\d+\s*(?:pk|packs?|ct))$/i;
const blend = /^(?:(?:indica|sativa|hybrid)\s+blend|mixed(?:\s+strains?)?)$/i;
const brandSuffix = /^(?:cannabis(?:\s+(?:co\.?|company))?|co\.?|company|llc\.?|inc\.?)\s+/i;
const leadingWeight = /^(?:\d+\s*\/\s*\d+|\d*\.?\d+)\s*g(?:m|rams?)?\s+(?=(?:vape|cartridge|disposable|pre[- ]?roll|jar)\b)/i;
const weightedGrade = /^\d*\.?\d+\s*g(?:m|rams?)?\s+(?:premium|popcorn|smalls?|shake|whole buds?)$/i;
const formNoise = /\b(?:cartridge|disposable|vape|concentrate|select grind|pre[- ]?rolls?|cured resin|live resin|cured rosin|vibey energy|tincture)\b/i;
const promotion = new RegExp(titleRules.promotion, 'i');
const potency = new RegExp(titleRules.potency, 'i');
const packaging = new RegExp(titleRules.packaging, 'i');
const stickLine = new RegExp(titleRules.stickLine, 'i');
const packSuffix = new RegExp(titleRules.packSuffix, 'i');
const unsafeHeading = value => potency.test(value) && !/[a-z]/i.test(value.replace(/(?:total|THC|CBD)/ig, ''))
  || menuDetail.test(value) || packaging.test(value) || weightedGrade.test(value);

// Menu labels that are absent from the brand directory, or name a product line.
const menuBrandNames = {
  'MNL': 'MN Loon',
  'Dope Cannabis': "D'Ope",
  'Green Box': 'Green Box',
  'Good Green': 'Good Green',
  'Leaf Line': 'Leaf Line',
  'Moonlight': 'Moonlight',
  'MoonWake Junction': 'Verist Fields',
  'OMA': 'Laketown Farms',
};

function brandIndex(directory) {
  const canonical = new Map(directory.map(brand => [normalize(brand.name), brand.name]));
  const names = new Map();
  for (const brand of directory) {
    for (const name of brand.aliases || []) {
      const key = normalize(name);
      if (!key) continue;
      if (names.has(key) && names.get(key) !== brand.name) names.set(key, null);
      else names.set(key, brand.name);
    }
  }
  for (const [key, name] of canonical) names.set(key, name);
  for (const [alias, brand] of Object.entries(menuBrandNames)) {
    if (!names.has(normalize(alias))) names.set(normalize(alias), brand);
  }
  const starts = new Map();
  const ends = new Map();
  for (const [key, brand] of names) {
    if (!brand) continue;
    const words = key.split(' ');
    for (const [index, word] of [[starts, words[0]], [ends, words.at(-1)]]) {
      index.set(word, Math.max(index.get(word) || 0, words.length));
    }
  }
  return {names, starts, ends};
}

function edgeBrand(text, index, side) {
  const edge = side === 'start' ? text.match(/^\S+/)?.[0] : text.match(/\S+$/)?.[0];
  if (!edge) return null;
  const normalizedEdge = normalize(edge).split(' ');
  const count = side === 'start' ? index.starts.get(normalizedEdge[0])
    : index.ends.get(normalizedEdge.at(-1));
  if (!count) return null;
  const words = [...text.matchAll(/\S+/g)];
  for (let size = Math.min(words.length, count); size > 0; size--) {
    const boundary = side === 'start' ? words[size - 1].index + words[size - 1][0].length
      : words[words.length - size].index;
    const key = normalize(side === 'start' ? text.slice(0, boundary) : text.slice(boundary));
    const brand = index.names.get(key);
    if (brand) {
      const remaining = side === 'start' ? text.slice(boundary) : text.slice(0, boundary);
      return {brand, remaining: remaining.replace(/^[\s:–-]+|[\s:–-]+$/g, '')};
    }
  }
  return null;
}

function dropObservedPrefix(text, label) {
  const words = text.match(/\S+/g) || [];
  const key = normalize(label);
  if (!key) return text;
  for (let length = 1; length < words.length; length++) {
    if (normalize(words.slice(0, length).join(' ')) === key) {
      return words.slice(length).join(' ').replace(/^[\s:–-]+/, '');
    }
  }
  return text;
}

function readTitle(offer, index, findStrain) {
  const {names} = index;
  const raw = String(offer.product_name || offer.strain || '').trim();
  const title = raw.replace(promotion, '');
  if (!title) return null;
  const form = String(offer.category || '').toLowerCase();
  const weight = Number(offer.package_g);
  const parts = title.split(/\s*\|\s*|\s+[–-]\s+/).filter(Boolean);
  let brand = names.get(normalize(offer.brand)) || '';
  let changed = raw !== title;
  const fields = parts.map(part => ({
    part, start: edgeBrand(part, index, 'start'), end: edgeBrand(part, index, 'end'),
  }));
  brand ||= fields.map(field => field.start || field.end).find(Boolean)?.brand || '';
  const pairedBrand = fields.map(field => field.end)
    .find(match => match?.brand !== brand && match?.remaining && names.get(normalize(match.remaining)) === brand);
  if (pairedBrand) brand = pairedBrand.brand;
  const candidates = [];
  let hasBlend = false;
  for (const {part, start, end} of fields) {
    let field = part;
    if (start && start.brand === brand) {
      field = start.remaining.replace(brandSuffix, '');
      const repeated = edgeBrand(field, index, 'start');
      if (repeated?.brand === brand) field = repeated.remaining;
      changed = true;
    }
    if (names.get(normalize(field))) {
      changed = true;
      continue;
    }
    if (blend.test(field)) {
      hasBlend = true;
      changed = true;
      continue;
    }
    if (!field || unsafeHeading(field) || /^\d+\s*mg$/i.test(field)) {
      changed = true;
      continue;
    }
    const old = field;
    if (!start && end && findStrain(dropObservedPrefix(end.remaining, offer.brand))) {
      field = dropObservedPrefix(field, offer.brand);
    }
    field = field.replace(potency, '').replace(packSuffix, '').trim();
    if (/pre[- ]?roll/i.test(form)) field = field.replace(stickLine, '');
    field = field.replace(leadingWeight, '').replace(leadingForm, '').replace(trailingForm, '').trim();
    if (form === 'flower' && weight > 0) {
      const size = field.match(/\s+(\d+\.\d+)$/);
      if (size && Number(size[1]) === weight) field = field.slice(0, size.index);
    }
    const suffix = field === part ? end : edgeBrand(field, index, 'end');
    if (suffix?.remaining && (suffix.brand === brand || (start && findStrain(suffix.remaining)))) {
      field = suffix.remaining;
      if (suffix.brand !== brand) brand = suffix.brand;
    }
    if (field !== old) changed = true;
    if (field && !unsafeHeading(field) && /[a-z]/i.test(field)) candidates.push(field);
  }
  if (!changed) return null;
  if (candidates.length === 1) return {strain: candidates[0], brand};
  if (!candidates.length && hasBlend) return {strain: 'Mixed Strains', brand};
  if (!candidates.length && brand) return {strain: 'Strain not specified', brand};
  return null;
}

export function menuIdentityResolver(directory, findStrain, existingIdentity) {
  const index = brandIndex(directory);
  return offer => {
    if (offer.reviewed_identity || offer.product_family_decision === 'owner_confirmed_exact_listing') return null;
    if (offer.brand && offer.product_name === offer.strain && offer.strain === offer.master_strain) return null;
    const parsed = readTitle(offer, index, findStrain);
    if (!parsed) return null;
    const existing = existingIdentity(offer);
    const priorName = existing.displayStrain;
    const priorBrand = existing.displayBrand;
    const parsedStrain = parsed.strain === 'Mixed Strains' ? null : findStrain(parsed.strain);
    const strain = parsedStrain?.canonical_name || parsed.strain;
    const master = findStrain(offer.master_strain);
    const priorKey = normalize(priorName);
    const hasResidue = (parsed.brand && [edgeBrand(priorName, index, 'start'), edgeBrand(priorName, index, 'end')]
      .some(match => match?.brand === parsed.brand))
      || formNoise.test(priorName) || unsafeHeading(priorName) || stickLine.test(priorName) || packSuffix.test(priorName)
      || /^(?:thc$|cannabis(?:\s+(?:co|company))?\b)/i.test(priorName)
      || /\s\d+\.\d+$/.test(priorName) || blend.test(priorName)
      || (parsedStrain && parsed.brand && priorKey.endsWith(' ' + normalize(parsed.strain)));
    const category = normalize(offer.category);
    const explicitBlend = strain === 'Mixed Strains';
    const brandOnly = strain === 'Strain not specified';
    const named = Boolean(parsedStrain);
    const corrected = normalize(parsed.strain) === priorKey || normalize(strain) === priorKey || explicitBlend || brandOnly
      || (hasResidue && (named || unsafeHeading(priorName) || stickLine.test(priorName) || packSuffix.test(priorName)
        || /^(?:vapes?|concentrates?)$/.test(category) || offer.product_name?.includes('|')));
    if (!corrected || (master && normalize(master.canonical_name) !== normalize(strain) && !hasResidue)) return null;
    if (strain === priorName && normalize(strain) === normalize(offer.strain)
      && (!parsed.brand || (parsed.brand === priorBrand && normalize(parsed.brand) === normalize(offer.brand)))) return null;
    return {strain, brand: parsed.brand};
  };
}
