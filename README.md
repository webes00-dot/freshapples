# MNtrees — Minnesota Strain Finder

Production website: https://mntrees.co/  
Canonical replacement source: `webes00-dot/freshapples` (main)

## Current architecture and release status

- **Public storefront:** Cloudflare Worker `mntrees`, Worker static assets, D1 `mntrees-reviews`. The current live HTML, CSS, JavaScript and Worker route handlers have been recovered into this repository.
- **Published market data:** versioned `data/site-data.json` and `data/catalog.json`, sourced from the current production site with checksums in `data/production-capture-manifest.json`.
- **Admin portal:** Cloudflare Worker `mntrees-admin`, D1 `mntrees-catalog-staging`. Its deployed code has been preserved in **private** Cloudflare recovery storage but is **not** yet a component of this public repository. Do not paste authentication/server implementation into a public repository.
- **Preview:** Worker `mntrees-recovery-preview`, separate reviews D1.
- **Collection and normalization engine:** a verified November 20 developer handoff and clean recovery candidate are preserved privately as archives, but scanner workflows have **not yet** been fully reconciled and imported into this repository.
- **Recovery storage:** private namespace `mntrees-private-recovery-snapshots` contains Worker source snapshots, current D1 table data and schema manifests, recovered static assets, and desktop/mobile screenshots.
- **Publication state:** GitHub storefront builds have passed CI checks; the consolidated architecture has **not** been deployed to production. Production remains on the validated existing Cloudflare Worker version.

## Building the public storefront

```bash
bash build.sh
```

Build outputs are in `dist/` and checked in a GitHub Actions artifact, accompanied by `dist-manifest.json`. The workflow `.github/workflows/verify-replacement-build.yml` runs on main and pull requests; build receipts are in `docs/LATEST_BUILD_VERIFICATION.json`.

`wrangler.jsonc` defines the current Worker routes, static asset binding, D1 reviews binding and preview environment. Do **not** deploy this source over production until current Admin Portal and scanner functionality, data integrity, private backups and live visual parity have been validated.

## Market pricing trends

`market-prices.js` now defines one three-series monthly line chart with flower, pre-roll and concentrate prices and no empty 2023–2025 axis span. The source observations are in `data/market-price-monthly.json`; the chart begins at the first observed month rather than inventing measurements.

## Recovery and release documentation

- `docs/PRODUCTION_RECOVERY_BASELINE_2026-11-22.md`: Cloudflare inventory and recovery gaps
- `docs/RECOVERY_SNAPSHOT_2026-11-22.md`: current database and Worker snapshot inventory
- `docs/CLEAN_RECOVERY_CANDIDATE_2026-11-22.md`: tested archive candidate and remaining release gates
- `docs/LATEST_BUILD_VERIFICATION.json`: most recent CI storefront build receipt

**Production release gate:** successful clean build, complete scan/admin source inventory, private D1 recovery restore test, desktop/mobile comparison, preview deployment and smoke tests, then controlled production deployment with rollback.

This repository and all scripts must remain independent of discontinued repositories and previous deployment workflows.
