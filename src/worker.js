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
