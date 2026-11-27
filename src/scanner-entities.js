import queries from './scanner-entity-queries.json';
import { scannerRun } from './scanner-ingest.js';

function validOperation(command) {
  if (!command || typeof command.operation !== 'string' || !Object.hasOwn(queries, command.operation)) return false;
  const { params, operation } = command;
  return Array.isArray(params) && params.length === queries[operation].params
    && params.every(value => value === null || Number.isSafeInteger(value)
      || (typeof value === 'string' && value.length <= 4000));
}

export async function scannerEntities(request, db) {
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });
  if (!await scannerRun(request)) return new Response('Unauthorized scanner workflow', { status: 401 });

  let commands;
  try {
    const input = await request.text();
    if (input.length > 100_000) return new Response('Entity batch too large', { status: 413 });
    commands = JSON.parse(input);
  } catch {
    return new Response('Invalid entity batch', { status: 400 });
  }
  if (!Array.isArray(commands) || !commands.length || commands.length > 25 || !commands.every(validOperation)) {
    return new Response('Invalid entity operations', { status: 400 });
  }
  try {
    const statements = commands.map(({ operation, params }) => {
      const statement = db.prepare(queries[operation].sql);
      return params.length ? statement.bind(...params) : statement;
    });
    const results = await db.batch(statements);
    return Response.json(results.map(result => result.results), { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    console.error('Scanner entity reconciliation failed', error);
    return new Response('Entity reconciliation failed', { status: 500 });
  }
}
