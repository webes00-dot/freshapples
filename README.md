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

## Scanner V2 replay

Use Python 3 with `google-auth` and `requests` for a live workbook read. Set
`MNTREES_MASTER_SHEET_ID` to the approved workbook ID and configure
`GOOGLE_SERVICE_ACCOUNT_JSON` in the runner with read access to that workbook.
Use a working directory outside the repository for captures and reports.

```bash
python3 scripts/scanner_v2_master.py --output "$RUN_DIR/master.json"
python3 scripts/scanner_v2_source_plan.py --master-snapshot "$RUN_DIR/master.json" --output "$RUN_DIR/source-plan.json"
python3 scripts/scanner_v2_capture.py --input "$RUN_DIR/rendered-menus.json" --output "$RUN_DIR/captured.json"
python3 scripts/scanner_v2_reconcile.py --master-snapshot "$RUN_DIR/master.json" --input "$RUN_DIR/captured.json" --output "$RUN_DIR/reconciled.json"
python3 scripts/scanner_v2_validate.py --input "$RUN_DIR/reconciled.json" --output "$RUN_DIR/validated.json"
```

Set `RUN_DIR` to an existing or new working directory. Supply
`rendered-menus.json` from a saved menu capture. A replay writes review reports
without changing the master workbook or publishing offers. Alias conflicts
are recorded in the runtime snapshot and left out of alias matching.
