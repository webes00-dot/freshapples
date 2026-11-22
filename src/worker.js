import { liveCatalog } from './live-catalog.js';
import { onRequestPost, onRequestGet } from '../functions/api/feedback.js';
import { onRequestGet as reviewsGet, onRequestPost as reviewsPost } from '../functions/api/reviews.js';
import { onRequestPost as flagReview } from '../functions/api/reviews/flag.js';
import { onRequestGet as moderationGet, onRequestPost as moderationPost } from '../functions/api/reviews/moderate.js';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
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
    const catalogPaths = ['/data/site-data.json', '/data/catalog.json', '/data/brands.json', '/data/retailer_locations.json'];
    if (request.method === 'GET' && env.CATALOG_DB && catalogPaths.includes(url.pathname)) {
      return liveCatalog(request, env);
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
