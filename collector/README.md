# MNtrees Fresh Collector — staging rebuild

This is a **fresh, conservative starting pipeline**, not a claim that retailer menus or collector integrations are working. No historical product records have been fabricated or recovered. All scans are staging-only. The production `data/listings.json` is **never overwritten** by this project.

## Inputs
- `config/menu_targets.csv`: 72 retailer location targets, including 11 previously confirmed/prior-audited direct menu links. These statuses are historical, not new connectivity checks.
- `config/retailers.csv`: 24 legacy connector configurations. Connector labels are **hints**, not implemented adapters.
- `config/naming_corrections.csv`: source-ID-approved corrections; applies only for matching retailer + source ID.
- `config/duplicate_review.csv`: adjudication history. The decisions are retained for adapter implementation; **no fuzzy automatic merges** are performed.
- `config/review_queue.csv`: unresolved product reviews to preserve.

## How to run on a machine with Internet

```bash
python collector.py --limit 3       # connection/extraction smoke test
python collector.py --delay 1.5     # entire target list
```

Uses Python standard library only. Honors site blocks/errors; do not bypass access restrictions or abuse vendor APIs. It requests public HTML sequentially, detects actual JSON-LD Product prices only, and stages all results in dated files under `data/`. Many JavaScript-heavy menu providers require platform-specific, permitted adapters; zero extracted products is **not** proof a menu has no products.

## Consolidation guardrails

1. Keep retailer-specific offers separate; consolidate only exact duplicate retailer + source identity.
2. Preserve distinct Float and Unbound brands, variants, package formats and separate preroll/flower categories.
3. Apply approved edits by exact source ID; no guesswork from near-matching product names.
4. Do not infer unknown grams, per-gram pricing, stock status, or tax. Do not treat displayed products as verified live inventory.
5. Compare 3.5g and 4g eighths together in industry summaries while retaining actual weight.
6. For price snapshot trends, require two dated, comparable snapshots.
7. If a scan fails or returns zero/partial coverage, preserve the last successful published dataset; **never replace it with empty output**.
8. Never silently merge products based on a 30% price tolerance; reviewed merge decisions must be explicitly mapped to product identities before implementation.

## Refresh deployment

The active `.github/workflows/scan.yml` provides scheduled staging scans (check the workflow for actual cron and execution results). It does not directly deploy to Cloudflare or write new entity records into the management Google Sheet. Deploy/promotion remains a separate signed-off process after adapter QA and completion checks.

## Next engineering step

Build provider-specific public-menu adapters (Sweed, Blaze, dispensary.shop, etc.) and validate against at least two live sample pages per provider. Capture stable product source IDs, package weights and original listing URLs, then make a QA-approved staging-to-production promotion with snapshot backup and rollback. Avoid pretending a reachable landing page equals a working catalog integration.