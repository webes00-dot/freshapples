# MNtrees V2: live D1 authority and scanner writeback gate (2026-11-22)

This is a verification note, not permission to publish staging observations.

## Verified current state
- Current editable Admin catalog: Cloudflare D1 `mntrees-catalog-staging`, id `457785f2-ab73-4858-b524-ba613a2b5388`.
- Read-only queries showed 1,149 strains, 75 brands, 277 retailers, 928 products, and 468 open review queue items.
- `sync_runs` has 0 rows; `price_observations` has 0 rows. Therefore do not claim scheduled scan-to-D1 ingestion is already operating.
- Admin audit log contains live edits: retailer updates, brand updates, strain updates and classification consolidations. These must not be overwritten by older Sheet-backed imports.
- `products.source_key` is a unique namespaced source identifier, not just a product title. Existing `products.raw_json` is a legacy positional array for some records, not a safe direct mapping to scanner dicts.
- `config/authority.json` still describes the older Google Sheets workflow. It must **not** be used as a writeback authority for the live D1 Admin catalog.

## Implemented safety stage
- `.github/workflows/scan.yml` runs read-only at 8 AM and 8 PM Central; workflow-change pushes run bounded scanner smoke tests.
- `collector/reconcile_d1_readonly.py` reads D1 current source keys and employee audit history, then classifies scanner candidates by exact source identity without making writes. Output is included in the scan artifact as `collector/data/d1_reconciliation.json`.
- A matching source suffix alone is not enough to authorize updates. Candidate retailer/store identity must be mapped to a unique D1 retailer; brand/strain must be resolved with approved aliases and stable IDs; package variant/category must remain distinct.
- **No production or D1 writes are enabled.** No change to the live Worker or Admin Worker was made by these commits.

## Before enabling D1 ingestion
1. Verify actual GitHub scan run logs and archive; handle denied D1 token read permissions if reported.
2. Establish a strict retailer + source product identity crosswalk and test it against sampled source records.
3. Add field ownership: scanner can update dated observations and independently validated offer prices only; human-managed names, aliases, classification, lineage, ownership, tags, and manual overrides stay protected.
4. Write to a dedicated append-only observations staging table, using provenance and uniqueness for `retailer+source+variant+observation time`; never update existing `products` directly from an unverified candidate.
5. Test migration, isolation, repeat ingestion/idempotence, backfill and rollback on disposable D1 before production schema changes.
6. Enable promotion only after explicit quality thresholds and last-good-data guarantees are met. Preserve unknowns in review queue instead of guessing.
