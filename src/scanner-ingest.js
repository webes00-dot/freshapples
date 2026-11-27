const UPSERT = `
INSERT INTO scanner_offers
    (offer_key, retailer_key, observed_at, price_cents, source_url, public_json)
SELECT 'scanner:' || json_extract(value, '$.id'),
       json_extract(value, '$.store_id'), json_extract(value, '$.checked_at'),
       json_extract(value, '$.price_cents'), json_extract(value, '$.url'), value
FROM json_each(?)
WHERE true
ON CONFLICT(offer_key) DO UPDATE SET
    observed_at = excluded.observed_at,
    price_cents = excluded.price_cents,
    source_url = excluded.source_url,
    public_json = excluded.public_json
WHERE excluded.observed_at > scanner_offers.observed_at
`;

const HISTORY = `
INSERT INTO price_observations
    (product_key, retailer_key, observed_at, price_cents, source_url, raw_json)
SELECT o.offer_key, o.retailer_key, o.observed_at, o.price_cents, o.source_url,
       json_object('source', 'scanner', 'workflow_run_id', ?2)
FROM json_each(?1) j
JOIN scanner_offers o ON o.offer_key = 'scanner:' || json_extract(j.value, '$.id')
    AND o.observed_at = json_extract(j.value, '$.checked_at')
WHERE NOT EXISTS (
    SELECT 1 FROM price_observations p WHERE p.product_key = o.offer_key
    AND p.retailer_key = o.retailer_key AND p.observed_at = o.observed_at
)
`;


const ISSUER = 'https://token.actions.githubusercontent.com';
const AUDIENCE = 'https://mntrees.co/api/internal/scanner-offers';
const WORKFLOW = 'webes00-dot/freshapples/.github/workflows/scan.yml@refs/heads/main';
const decoder = new TextDecoder();
const encoder = new TextEncoder();
let keyset;
let keysExpireAt = 0;

function base64url(value) {
  return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), char => char.charCodeAt(0));
}

async function getSigningKey(kid) {
  if (Date.now() >= keysExpireAt) {
    const response = await fetch(ISSUER + '/.well-known/jwks');
    if (!response.ok) throw Error('GitHub signing keys unavailable');
    keyset = (await response.json()).keys;
    keysExpireAt = Date.now() + 300_000;
  }
  const key = keyset.find(key => key.kid === kid && key.kty === 'RSA' && (!key.use || key.use === 'sig'));
  return key && crypto.subtle.importKey(
    'jwk', key, {name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256'}, false, ['verify'],
  );
}

export async function scannerRun(request) {
  const token = request.headers.get('Authorization')?.match(/^Bearer ([A-Za-z0-9._-]+)$/)?.[1];
  const parts = token?.split('.') || [];
  if (parts.length !== 3 || token.length > 16_384) return null;
  try {
    const [header, body, signature] = parts;
    const {kid, alg} = JSON.parse(decoder.decode(base64url(header)));
    if (alg !== 'RS256' || typeof kid !== 'string') return null;
    const claims = JSON.parse(decoder.decode(base64url(body)));
    const now = Math.floor(Date.now() / 1000);
    if (
      claims.iss !== ISSUER || claims.aud !== AUDIENCE ||
      claims.repository_id !== '1466619489' || claims.repository_owner_id !== '359554322' ||
      claims.workflow_ref !== WORKFLOW || claims.ref !== 'refs/heads/main' ||
      !['push', 'schedule', 'workflow_dispatch'].includes(claims.event_name) ||
      !Number.isInteger(claims.exp) || claims.exp <= now ||
      !Number.isInteger(claims.nbf) || claims.nbf > now ||
      !/^\d+$/.test(claims.run_id)
    ) return null;

    const key = await getSigningKey(kid);
    if (!key || !await crypto.subtle.verify(
      'RSASSA-PKCS1-v1_5', key, base64url(signature), encoder.encode(header + '.' + body),
    )) return null;
    const runId = Number(claims.run_id);
    return Number.isSafeInteger(runId) ? runId : null;
  } catch {
    return null;
  }
}

function validRow(row) {
  if (!row || typeof row !== 'object') return false;
  const {id, store_id, checked_at, price_cents, url, product_name} = row;
  return typeof id === 'string' && /^[a-f0-9]{20}$/.test(id)
    && typeof store_id === 'string' && Boolean(store_id)
    && typeof checked_at === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/.test(checked_at)
    && Number.isInteger(price_cents) && price_cents > 0 && price_cents < 1_000_000
    && typeof url === 'string' && /^https?:\/\//.test(url)
    && typeof product_name === 'string' && Boolean(product_name);
}

export async function ingestScannerOffers(request, db) {
  if (request.method !== 'POST') return new Response('Method not allowed', {status: 405});
  const runId = await scannerRun(request);
  if (!runId) return new Response('Unauthorized scanner workflow', {status: 401});
  const input = await request.text();
  if (input.length > 300_000) return new Response('Scan batch too large', {status: 413});
  let rows;
  try {
    rows = JSON.parse(input);
  } catch {
    return new Response('Invalid scan batch', {status: 400});
  }
  if (!Array.isArray(rows) || !rows.length || rows.length > 100 || !rows.every(validRow)
      || new Set(rows.map(row => row.id)).size !== rows.length) {
    return new Response('Invalid scan batch', {status: 400});
  }
  const batch = JSON.stringify(rows);
  const [offers, observations] = await db.batch([
    db.prepare(UPSERT).bind(batch),
    db.prepare(HISTORY).bind(batch, runId),
  ]);
  return Response.json({
    listings_written: offers.meta.changes,
    price_observations: observations.meta.changes,
  });
}
