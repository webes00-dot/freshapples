# MNtrees production baseline and clean architecture recovery
Captured 2026-11-22. **Inventory only; this is NOT a full production backup or release authorization.**

## Canonical targets
- Sole replacement source repository: `webes00-dot/freshapples` (main).
- Production hostname: `mntrees.co` -> Cloudflare Worker `mntrees`.
- Worker `mntrees` has static asset binding `ASSETS` and D1 binding `REVIEWS_DB` -> `mntrees-reviews`.
- Worker `mntrees-admin` has D1 binding `CATALOG_DB` -> `mntrees-catalog-staging`.
- Separate worker: `mntrees-recovery-preview`, bound to D1 `mntrees-recovery-preview-reviews`.
- No Worker schedules were reported on these three scripts. This does NOT rule out GitHub Actions schedules or external schedulers.
- Production `mntrees` deployment: `8d645369-68de-4c7c-bd2a-1748d9a536ca`, version `5406d985-676f-470d-b48e-062f412a9458`, created 2026-11-22T15:58:04Z.
- Production Worker annotations: commit `0f38226978017ac84f9b5f1063c379d9d0fdb2a5`, message "Publish verified Strain Master profile links"; annotation is **not** proof the repository source is complete.
- `mntrees-admin` last observed deployment at 2026-11-22T18:51:42Z.
- D1 databases: `mntrees-catalog-staging`, `mntrees-reviews`, `mntrees-recovery-preview-reviews`.

## Confirmed recovery gap
The Cloudflare Worker content download for `mntrees` contains five API/Worker script modules (including `src/worker.js`), **not the static assets** that produce the published design. The `ASSETS` binding is present. No complete downloadable asset bundle was obtained, and no verified D1 SQL backups were created in this operation. The live design is therefore **not yet backed up**.

The GitHub README describes `build.sh`, `app.js`, `src/worker.js` and the development handoff at `docs/DEVELOPER_HANDOFF_2026-11-20.md`, but these paths were unavailable on the current default branch when checked. The available files include `README.md` and `data/market-price-history.json`. Do not use the replacement repository to deploy until it is reconciled with production.

## Clean deployment requirements (not yet achieved)
1. Recover all current static assets and API/Worker source from the production deployment, including HTML, CSS, JavaScript, images, redirects, and configs. Preserve checksums and screenshots of desktop/mobile layout.
2. Recover the separately maintained admin portal Worker source and its auth configuration without committing secrets.
3. Export complete D1 SQL schema/data snapshots for every production database and test restoring to temporary databases; use time-travel bookmarks as an additional safety measure.
4. Consolidate **only current** code into the replacement repository, including build scripts, normalized rules, scan pipeline, schema migrations, and CI.
5. Remove all obsolete remote references and workflows. Ensure clean checkout reproduces both website and admin portal against staging databases.
6. Run functional, visual, mobile, API, authorization, normalization and regression checks. Compare against live production before promoting.
7. Integrate the monthly line chart for flower, pre-rolls and concentrates. Start plotted x-axis at the earliest real observed price month, preserving 2023-08 as era metadata without visually blank months.
8. Publish using a single controlled deployment with rollback, backup manifest, and production checks; keep canonical ZIP / release artifact and database exports.
9. Document the future code->build->preview->production procedure, plus scheduled data exports and restore drills.

## Current decision
Production must remain unchanged until static assets and data are captured and a new build matches the live design. Nothing in this inventory should be represented as a completed backup or redeployment.
