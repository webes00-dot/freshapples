# MNtrees replacement production release — 2026-11-22

## Production release result

- **Build:** `ea1b5d4f-0a08-4a63-a3f1-4a746eab87e7`
- **Cloudflare Builds outcome:** `stopped` / `success`
- **Source:** `webes00-dot/freshapples` branch `main`, not the discontinued repository
- **Production Worker:** `mntrees`, version `6c744a2f-17cf-462c-ad04-a776bab71d9f`
- **Released:** 2026-11-22 21:36:33 UTC
- **Production hostname:** `mntrees.co`
- **Bindings preserved:** `ASSETS`, `REVIEWS_DB` -> `mntrees-reviews` (D1 ID `9d62cb7c-0f35-4e66-a47f-9cb3cb465a49`)
- **Admin Portal:** `mntrees-admin` unchanged, version `860bf341-a11a-42ab-9b7d-af56be2b9868`
- **Default production deploy gate:** no-op `echo "MNtrees production release gated; preview verification required"`; deliberate manual release required.

## Pre-release verification

1. Cloudflare fetched and built the replacement repository from main, deploying isolated preview `mntrees-recovery-preview` version `7f696772-b56a-4242-a9aa-d9cb3924145d`.
2. Frontend production / preview exact SHA-256 parity for 16 static pages/scripts/data artifacts; updated `market-prices.js` is intended difference.
3. All five production Worker source modules match the repository byte-for-byte (independent checksums).
4. Browser rendering at widths 390 and 1440 matched production homepage dimensions, text length, navigation geometry and zero horizontal overflow.
5. Public read-only reviews API, invalid-method handling, unauthorized moderation responses matched in production and preview.
6. Preview line chart displayed 3 SVG series and 21 monthly observations, with first month August 2025.
7. Disposable catalog restore drill passed 13 of 13 table counts (9,678 rows), zero foreign key violations. Temporary test database deleted.
8. Encrypted D1 snapshot transferred to public GitHub as six ciphertext shards, all read back at exact expected lengths and matching chunk hashes; source encrypted blobs decrypted, decompressed and verified against SHA-256 digests.
9. Three encrypted deployed Worker archives (site, Admin, preview) verified by GitHub readback, AES-GCM decrypt, gunzip and SHA-256. Private decryption key stored separately in owner ChatGPT Library.

## Post-release verification

Cloudflare's deployment API confirmed production version `6c744a2f-17cf-462c-ad04-a776bab71d9f`, successful build, restored safe deploy gate and retained production D1 binding. A post-release browser check was **not completed** because the Cloudflare Browser Rendering API exhausted its quota (HTTP 429 requesting an approximately 2.4-hour wait), and independent public web fetch was inaccessible. Do not claim live page content was independently inspected after promotion. The built files/preview were verified pre-release and deployed successfully.

## Remaining architecture work (NOT complete)

- Scanner source and tests were copied to the replacement repository, but several raw supporting datasets, D1 edit writeback and unified scan scheduling still require a full test. `config/authority.json` still refers to the historical Google Sheets editorial workflow, while new D1 Admin catalog is the current source. Do **not** turn on legacy scan schedules or let stale source overwrite D1 edits.
- Admin Portal deployed Worker is preserved as encrypted source (not plaintext in the public repository); secure reproducible Admin build and Google login/auth verification still need implementing. Existing Admin production deployment was not altered.
- Schedule recurring off-platform private D1 exports/backup retention and periodic clean restore drills. The current recovery snapshot is a dated one-time backup.
- Verify market pricing page directly after Cloudflare Browser Rendering rate limit clears. Avoid claiming that the current public UI has been post-deployment smoke-tested.
- Audit Cloudflare's API redacted build-time secrets and review moderation admin authorization before considering this a fully functional centralized release mechanism.

This release is a successful **public storefront migration and controlled deployment**, **not** the end of scanner/Admin architecture consolidation.
