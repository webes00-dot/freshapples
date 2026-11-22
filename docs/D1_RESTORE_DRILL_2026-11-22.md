# D1 catalog recovery drill — 2026-11-22

**Result: PASS — 13/13 table counts matched; 9,678/9,678 rows restored; 0 foreign-key violations.**

## Scope
Only the **new, current MNtrees** catalog database was tested. No V1 database, old GitHub repository, retired workflow, or legacy migration was used.

Snapshot source: private Cloudflare KV namespace `mntrees-private-recovery-snapshots`, prefix `2026-11-22/d1/catalog/`, with schema manifest and 55 table-data chunks. Database originally bound as `CATALOG_DB` on `mntrees-admin` and named `mntrees-catalog-staging`.

## Procedure and verification
1. Created isolated disposable D1 database `mntrees-restore-test-20261122`.
2. Replayed 13 `CREATE TABLE` statements and one index definition from the saved `sqlite_master` manifest.
3. Loaded 6,301 `source_rows` records and all remaining 3,377 records, including parent retailers before 928 products to satisfy foreign-key constraints. Inserts used SQLite JSON1 `json_each(?)` for safe parameterization and batching.
4. Queried `COUNT(*)` in every restored table, compared with preserved manifest.
5. Queried `PRAGMA foreign_key_check` — **0** reported violations.
6. Deleted the isolated test database after validation (confirmed successful deletion API response). No test database was retained.

## Per-table restored row counts
| Table | Restored / expected |
| --- | ---: |
| admin_audit_log | 372 / 372 |
| brands | 75 / 75 |
| entity_aliases | 29 / 29 |
| migrations | 1 / 1 |
| ownership_groups | 37 / 37 |
| price_observations | 0 / 0 |
| products | 928 / 928 |
| retailers | 277 / 277 |
| review_queue | 468 / 468 |
| rules | 41 / 41 |
| source_rows | 6301 / 6301 |
| strains | 1149 / 1149 |
| sync_runs | 0 / 0 |
| **Total** | **9678 / 9678** |

## Limitations
- This validates **snapshot data restoration into a fresh D1** and referential integrity at the captured time; it does **not** establish that a native SQL export or independently stored archive is complete, that indexes and triggers beyond those captured exist, or that the snapshot is current after additional edits.
- Reviews and preview reviews were empty during the snapshot and were not populated in the catalog drill.
- The static website code, Admin Worker, scanner source, production automation and preview design still require full clean-repository reconciliation before a safe production release.
- The private KV namespace is interim recovery storage and is **not** a substitute for automated, versioned off-platform backups.

**Release gate:** no production redeployment until missing Admin/scanner code and current frontend assets are reconciled and a preview passes functional and visual parity tests.
