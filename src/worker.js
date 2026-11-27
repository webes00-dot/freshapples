import { ingestScannerOffers } from './scanner-ingest.js';
import { scannerEntities } from './scanner-entities.js';
import { liveCatalog } from './live-catalog.js';
import { onRequestPost, onRequestGet } from '../functions/api/feedback.js';
import { onRequestGet as reviewsGet, onRequestPost as reviewsPost } from '../functions/api/reviews.js';
import { onRequestPost as flagReview } from '../functions/api/reviews/flag.js';
import { onRequestGet as moderationGet, onRequestPost as moderationPost } from '../functions/api/reviews/moderate.js';


// Cache assembled catalog JSON at the edge so repeated page loads do not
// re-read D1 and recompute all retailer, brand, and strain joins.
// This caches only successful D1 results. Existing static fallback is unchanged.
async function cachedLiveCatalog(request, env, ctx) {
  const url = new URL(request.url);
  const cacheKey = new Request(url.origin + url.pathname + '?edge-catalog-v1');
  const cache = caches.default;
  try {
    const cached = await cache.match(cacheKey);
    if (cached) {
      const headers = new Headers(cached.headers);
      headers.set('Cache-Control', 'no-store');
      headers.set('X-MNtrees-Catalog-Cache', 'HIT');
      return new Response(cached.body, {status: cached.status, headers});
    }
  } catch (error) {
    console.warn('Catalog edge cache read failed', error);
  }

  const response = await liveCatalog(request, env);
  // Do not cache errors or static fallback: a transient failure must not replace
  // the last valid catalog assembly in the edge cache.
  if (response.ok && response.headers.get('X-MNtrees-Catalog-Source') === 'd1') {
    const headers = new Headers(response.headers);
    headers.set('Cache-Control', 'public, max-age=300');
    const cacheable = new Response(response.clone().body, {
      status: response.status, headers
    });
    ctx.waitUntil(cache.put(cacheKey, cacheable).catch(error => {
      console.warn('Catalog edge cache write failed', error);
    }));
  }
  return response;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api/internal/scanner-offers') {
      return ingestScannerOffers(request, env.CATALOG_DB);
    }
    if (url.pathname === '/api/internal/scanner-entities') {
      return scannerEntities(request, env.CATALOG_DB);
    }
    if (url.pathname === '/api/feedback') {
      if (request.method === 'POST') return onRequestPost({request, env});
      if (request.method === 'GET') return onRequestGet();
      return new Response('Method not allowed', {status: 405, headers: {'allow':'GET, POST'}});
    }
    if (url.pathname === '/api/reviews') {
      if (request.method === 'GET') return reviewsGet({request, env});
      if (request.method === 'POST') return reviewsPost({request, env});
      return new Response('Method not allowed', {status: 405});
    }
    if (url.pathname === '/api/reviews/flag' && request.method === 'POST') return flagReview({request, env});
    if (url.pathname === '/api/reviews/moderate') {
      if (request.method === 'GET') return moderationGet({request, env});
      if (request.method === 'POST') return moderationPost({request, env});
      return new Response('Method not allowed', {status: 405});
    }
    if (url.pathname === '/api/catalog-test' && request.method === 'GET') {
      if (!env.CATALOG_DB) return new Response('Catalog database not configured', {status: 503});
      const result = await env.CATALOG_DB.prepare(
        "SELECT p.source_key AS id, r.display_name AS retailer, COALESCE(s.canonical_name, json_extract(p.raw_json, '$[10]')) AS strain, COALESCE(b.canonical_name, json_extract(p.raw_json, '$[11]')) AS brand, json_extract(p.raw_json, '$[5]') AS category, CAST(json_extract(p.raw_json, '$[6]') AS REAL) AS grams, CAST(json_extract(p.raw_json, '$[7]') AS REAL) AS price, json_extract(p.raw_json, '$[8]') AS url FROM products p JOIN retailers r ON r.id = p.retailer_id LEFT JOIN strains s ON s.id = p.canonical_strain_id LEFT JOIN brands b ON b.id = p.brand_id WHERE p.source_key LIKE 'scanner:%' ORDER BY p.id LIMIT 6"
      ).all();
      return Response.json({products: result.results || []}, {headers: {'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*'}});
    }
    const catalogPaths = ['/data/site-data.json', '/data/catalog.json', '/data/brands.json', '/data/retailer_locations.json', '/data/published-strains.json'];
    if (request.method === 'GET' && env.CATALOG_DB && catalogPaths.includes(url.pathname)) {
      return cachedLiveCatalog(request, env, ctx);
    }
    // The former site used /map; keep one canonical map entrypoint.
    if (url.pathname === '/map' || url.pathname === '/map/') {
      return Response.redirect(new URL('/map.html', url), 302);
    }
    const response = await env.ASSETS.fetch(request);
    if (url.pathname === '/map.html' || url.pathname.startsWith('/data/')) {
      const headers = new Headers(response.headers);
      headers.set('Cache-Control', 'no-store, max-age=0');
      return new Response(response.body, {status: response.status, statusText: response.statusText, headers});
    }
    return response;
  }
};
