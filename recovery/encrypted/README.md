# MNtrees encrypted independent recovery backup (2026-11-22)

This directory holds **AES-256-GCM encrypted** source and database snapshots. It is intentionally in the **current replacement GitHub repository**; none of the plaintext Admin Worker code or D1 catalog records should be committed publicly.

## Contents

- `workers/mntrees.aes256gcm.json`, `workers/mntrees-admin.aes256gcm.json`, `workers/mntrees-recovery-preview.aes256gcm.json`: deployed Worker sources (multipart archives)
- `d1-catalog-2026-11-22-part1.aes256gcm.json` and `part2`: encrypted snapshot manifest, nonce, sizes, SHA-256 digest and shard names
- `shards/catalog-2026-11-22-part{1,2}-shard{0,1,2}.b64`: complete ciphertext for the two D1 parts (six shards total)
- `scripts/decrypt_recovery_snapshot.py` at repository root: offline decryption, authenticity checks, recovery of Worker source files, SQLite catalog restoration, portable SQL dump generation and row-count / FK verification

## Key handling

A separate 256-bit recovery key was saved to the owner's **private ChatGPT Library** as `MNtrees_Private_Recovery_Key_2026-11-22.json`. This key is NOT stored in this public GitHub repository or in Cloudflare. Keep a second private copy offline. Without the key, the encrypted contents cannot be decrypted. Do not put the key in CI logs, GitHub Actions secrets that print values, tickets, or public code.

## Local recovery

```bash
python3 -m pip install cryptography
python3 scripts/decrypt_recovery_snapshot.py \
  --key-file /secure/MNtrees_Private_Recovery_Key_2026-11-22.json \
  --output /secure/mntrees-recovered
```

The output includes decrypted Worker multipart/source files, all 58 dated D1 snapshot objects, `catalog-2026-11-22.sqlite3`, `catalog-2026-11-22.sql`, and `RESTORE_REPORT.json`. Run it only on a **trusted private computer** and keep decrypted outputs outside the public repository. The catalog contains **9,678 records across 13 tables** at capture time. Production and preview review tables were empty.

## Verification accomplished

1. Live D1 catalog snapshot successfully restored into a disposable Cloudflare D1 database: **13/13 table counts**, 9,678 records, **0 foreign key violations**. Temporary database was deleted.
2. Original two encrypted catalog parts decrypted/decompressed successfully and SHA-256 checksums matched, recovering 58 source KV objects and 9,678 row records.
3. All six ciphertext shards read back from GitHub and matched the privately staged ciphertext for their exact ranges; total encoded lengths matched **454,400** and **492,240** characters.
4. Each of the three encrypted Worker archives was fetched back from GitHub, decrypted and decompressed, with SHA-256 verification and expected multipart source part counts.
5. The offline Python recovery script passed a synthetic test of encryption, compression, SQLite restoration and row-count validation. A full **offline** SQLite restore using GitHub shard files on the owner's computer has not yet been executed.

## Release boundaries

The public website, scripts, catalog read models, and recovery materials are versioned in this replacement GitHub repository. The private Admin Portal code is included only in its encrypted recovery archive; the Admin Worker is still deployed directly on Cloudflare. The imported scanner is **not yet approved for unattended scheduling**: its recovered `config/authority.json` still refers to the historical editorial spreadsheet, while the current Admin Portal's catalog authority is the new D1 database. Normalize those authority rules and test writeback before enabling scans.

No previous repository or V1 database is required to perform this recovery.
