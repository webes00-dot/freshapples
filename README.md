# MNtrees — Minnesota Strain Finder

Production website: https://mntrees.co/  
Canonical replacement source: `webes00-dot/freshapples` (main)

## Current architecture and release status

- **Public storefront:** Cloudflare Worker `mntrees`, Worker static assets, D1 `mntrees-reviews`. The current live HTML, CSS, JavaScript and Worker route handlers have been recovered into this repository, and production was redeployed from this source on 2026-11-22.
- **Published market data:** versioned `data/site-data.json` and `data/catalog.json`, sourced from the current production site with checksums in `data/production-capture-manifest.json`.
- **Admin portal:** Cloudflare Worker `mntrees-admin`, D1 `mntrees-catalog-staging`. Its deployed code has been preserved in **private** Cloudflare recovery storage and as **AES-256-GCM encrypted versioned source** in `recovery/encrypted/workers/`; the decryption key remains separate in the owner's private Library. It is not yet integrated into a reproducible Admin deployment pipeline. Do not paste authentication/server implementation into a public repository.
- **Preview:** Worker `mntrees-recovery-preview`, separate reviews D1.
- **Collection and normalization engine:** 77 recovered scanner, normalization, test and supporting modules are now versioned here, but unattended scheduling remains blocked until D1 authority and writeback have been reconciled.
- **Recovery storage:** private namespace `mntrees-private-recovery-snapshots` contains Worker source snapshots, current D1 table data and schema manifests, recovered static assets, and desktop/mobile screenshots.
- **Publication state:** Replacement storefront was deployed to production on 2026-11-22 (see `docs/PRODUCTION_RELEASE_2026-11-22.md`); this does not mean scanner/Admin consolidation is complete.

## Building the public storefront

```bash
bash build.sh
```

Build outputs are in `dist/` and checked in a GitHub Actions artifact, accompanied by `dist-manifest.json`. The workflow `.github/workflows/verify-replacement-build.yml` runs on main and pull requests; build receipts are in `docs/LATEST_BUILD_VERIFICATION.json`.

`wrangler.jsonc` defines the current Worker routes, static asset binding, D1 reviews binding and preview environment. Production storefront was deployed from this repository. Before any **new** release, verify current Admin Portal and scanner functionality, data integrity, private backups and live visual parity.

## Market pricing trends

`market-prices.js` now defines one three-series monthly line chart with flower, pre-roll and concentrate prices and no empty 2023–2025 axis span. The source observations are in `data/market-price-monthly.json`; the chart begins at the first observed month rather than inventing measurements.

## Recovery and release documentation

- `docs/PRODUCTION_RECOVERY_BASELINE_2026-11-22.md`: Cloudflare inventory and recovery gaps
- `docs/RECOVERY_SNAPSHOT_2026-11-22.md`: current database and Worker snapshot inventory
- `docs/CLEAN_RECOVERY_CANDIDATE_2026-11-22.md`: tested archive candidate and remaining release gates
- `docs/LATEST_BUILD_VERIFICATION.json`: most recent CI storefront build receipt

**Storefront release**: clean build, D1 recovery restore, 16-file static byte parity, desktop/mobile DOM parity and isolated preview succeeded, followed by one controlled production redeployment. **Scanner staging:** `.github/workflows/scan.yml` now schedules read-only 8 AM / 8 PM Central scans and archives outputs without publication or D1 writes; its first successful scheduled run still needs verification. **Remaining gates:** scanner D1 writeback, secure Admin deploy pipeline, full post-release browser checks and recurring off-platform backup automation. Do not enable unattended *production publishing* until D1 authority and edit preservation are verified.

This repository and all scripts must remain independent of discontinued repositories and previous deployment workflows.
