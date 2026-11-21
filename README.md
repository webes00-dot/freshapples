# MNtrees — Minnesota Apple Variety Finder

The recovery preview uses the pre-V2 app and historical public menu and orchard directory snapshots. The original observations show advertised prices at the time they were checked. Stock is unverified.

## Build and verify

Run from the repository root with Node and Python 3.

```bash
bash build.sh
node tests/catalog-model.test.cjs
node tests/catalog-grouping.test.js
node tests/mn-loon.test.js
```

The build writes the site to `dist/`. The Cloudflare Worker entry point is `src/worker.js`.

## Cloudflare preview

Use a separate Worker named `mntrees-recovery-preview`, with root `/` and build command `bash build.sh`. Use its Cloudflare URL to verify the site before any domain change.

Reviews need a preview D1 database bound as `REVIEWS_DB` with the migration from `migrations/`. Feedback delivery requires its existing Cloudflare configuration. Price history, broader variety enrichment, and live master sync require additional recovery work.
