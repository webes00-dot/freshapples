# MNtrees new-system recovery snapshot — 2026-11-22

**Scope:** Current Cloudflare setup and new D1 databases only. No Version 1 database recovery, repository references, or dependencies.

## Private backup created
Cloudflare Workers KV namespace `mntrees-private-recovery-snapshots` stores a dated private snapshot under `2026-11-22/`:

- Production Worker multipart source: `workers/mntrees/deployed-source.multipart`
- Admin Worker multipart source: `workers/mntrees-admin/deployed-source.multipart`
- Preview Worker multipart source: `workers/mntrees-recovery-preview/deployed-source.multipart`
- Catalog D1 schema/index definitions and table row counts: `d1/catalog/manifest.json`
- Catalog row-data chunks, 200 rows each: `d1/catalog/<table>/<part>.json`
- Empty reviews and preview-reviews D1 schema manifests: `d1/reviews/manifest.json` and `d1/preview_reviews/manifest.json`.

**Read-back verified:** all 55 catalog table JSON chunks retrieved and parsed; row totals matched live D1 table counts at the time of the audit. 9,678 catalog table rows in all, including 6,301 source rows, 1,149 strains, 928 products, 277 retailers, 75 brands, 41 rules, and 468 review queue rows. 61 KV objects were listed in the date-scoped snapshot (55 populated data objects + three D1 schema manifests + three Worker source files). Private KV is a temporary disaster-recovery copy, **not** the master version-controlled source repository.

Cloudflare's D1 SQL export API separately reported successful exports for each of the three databases, but the generated short-lived signed download URLs were not retrievable into persistent storage from this connector. Therefore **SQL dumps are not yet verified as stored backups**.

## Current obstacles to a trustworthy master release
1. `mntrees.co` is served by the `mntrees` Worker with a separate Cloudflare static assets binding (`ASSETS`). The API download of Worker script modules does not return the deployed website's HTML/CSS/JS/image assets.
2. The replacement GitHub repository does not have the active build and application files in the README's listed paths, so it cannot currently be considered a complete reproducible build.
3. The current GitHub repository is public. Private D1 data and server-side Admin Worker source should **not** be copied into it without a security review and an explicit repository visibility decision.
4. Cloudflare R2 is not enabled in this account. The KV snapshot is a protective interim measure, not a long-term archive or verified SQL restore.
5. A restored and visually compared preview build has not yet been completed. No new production deployment was attempted.

## Next release gate
Recover deployed static assets and current code into a safe source workspace; obtain durable binary SQL exports, perform a restore test, compare desktop/mobile live design and API behavior, then implement GitHub -> preview -> production with a rollback and release artifact. **No production changes until the master build has passed those checks.**
