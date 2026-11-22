# D1 read-only inventory — 2026-11-22

Cloudflare account inspection confirmed these existing databases and table names:

| Database | Current application | Tables (excluding internal _cf_KV and sqlite_sequence) |
| --- | --- | --- |
| mntrees-catalog-staging | mntrees-admin (CATALOG_DB) | admin_audit_log, brands, entity_aliases, migrations, ownership_groups, price_observations, products, retailers, review_queue, rules, source_rows, strains, sync_runs |
| mntrees-reviews | mntrees (REVIEWS_DB) | feedback, review_flags, reviews |
| mntrees-recovery-preview-reviews | mntrees-recovery-preview (REVIEWS_DB) | feedback, review_flags, reviews |

All three databases were queried successfully. The D1 API returned time-travel bookmarks, establishing that recovery checkpoints can be read. **This was not a SQL export, restore test, or database data backup**.

Static assets were not retrievable from the Worker source download, so current production design and its complete files remain to be recovered before a full master backup or redeployment can be claimed.

No live applications or D1 rows were modified in this audit.
