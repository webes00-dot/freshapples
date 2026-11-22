#!/usr/bin/env python3
"""Decrypt and verify the MNtrees self-contained 2026-11-22 recovery snapshot.

The public GitHub source contains AES-256-GCM ciphertext only. The decryption
key belongs in a PRIVATE file, separately downloaded from the user's Library.
No network or Cloudflare credentials are needed to restore this archive.

Usage:
  python3 -m pip install cryptography
  python3 scripts/decrypt_recovery_snapshot.py \
      --key-file /private/MNtrees_Private_Recovery_Key_2026-11-22.json \
      --output /private/MNtrees_Restored_2026-11-22
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
ENCRYPTED = ROOT / "recovery" / "encrypted"


def decode_archive(manifest: dict, key: bytes, root: Path) -> bytes:
    if manifest.get("algorithm") != "AES-256-GCM":
        raise ValueError("Unexpected cipher")
    if manifest.get("compression") != "gzip":
        raise ValueError("Unexpected compression")
    if "shard_paths" in manifest:
        pieces = []
        for name in manifest["shard_paths"]:
            path = root / name
            resolved = path.resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise ValueError("Unsafe shard path")
            pieces.append(path.read_text(encoding="ascii").strip())
        encoded = "".join(pieces)
    else:
        encoded = manifest["ciphertext_base64"]
    expected_len = 4 * ((manifest["compressed_bytes"] + 16 + 2) // 3)
    if len(encoded) != expected_len:
        raise ValueError(f"Encrypted file truncated: {len(encoded)} vs {expected_len}")
    cipher = base64.b64decode(encoded, validate=True)
    iv = base64.b64decode(manifest["iv_base64"], validate=True)
    compressed = AESGCM(key).decrypt(iv, cipher, None)
    if len(compressed) != manifest["compressed_bytes"]:
        raise ValueError("Compressed byte length mismatch")
    clear = gzip.decompress(compressed)
    if len(clear) != manifest["uncompressed_bytes"]:
        raise ValueError("Uncompressed byte length mismatch")
    if base64.b64encode(hashlib.sha256(clear).digest()).decode() != manifest["clear_sha256_base64"]:
        raise ValueError("SHA256 checksum mismatch")
    return clear


def restore_sqlite(objects: dict[str, str], dest: Path) -> dict[str, int]:
    manifest_key = next((k for k in objects if k.endswith("/d1/catalog/manifest.json")), None)
    if manifest_key is None:
        raise ValueError("Missing catalog schema manifest")
    manifest = json.loads(objects[manifest_key])
    if dest.exists():
        raise ValueError(f"Refusing to overwrite restored database: {dest}")
    connection = sqlite3.connect(dest)
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        for entry in manifest["schema"]:
            if entry["type"] == "table":
                connection.execute(entry["sql"])
        for entry in manifest["schema"]:
            if entry["type"] == "index":
                connection.execute(entry["sql"])
        counts = {c["table"]: c for c in manifest["counts"]}
        order = [c["table"] for c in manifest["counts"]]
        if "products" in order:
            order.remove("products")
            order.append("products")
        result = {}
        for name in order:
            count = counts[name]
            for idx in range(count["parts"]):
                key = f"2026-11-22/d1/catalog/{name}/{idx:04}.json"
                if key not in objects:
                    raise ValueError(f"Missing table data: {key}")
                data = json.loads(objects[key])
                rows = data["rows"]
                if not rows:
                    continue
                columns = list(rows[0])
                quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
                placeholders = ", ".join("?" for _ in columns)
                statement = f'INSERT INTO "{name}" ({quoted}) VALUES ({placeholders})'
                values = [tuple(json.dumps(row[k]) if isinstance(row.get(k), (dict, list)) else row.get(k) for k in columns) for row in rows]
                connection.executemany(statement, values)
            actual = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            if actual != count["rows"]:
                raise ValueError(f"Table mismatch: {name} {actual} != {count['rows']}")
            result[name] = actual
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"Foreign key violations: {violations[:5]}")
        connection.commit()
        return result
    except Exception:
        connection.close()
        dest.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def extract_worker_parts(data: bytes, directory: Path):
    raw = data.decode("utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "deployed-source.multipart").write_bytes(data)
    first_line = raw.split("\r\n", 1)[0]
    if not first_line.startswith("--"):
        return 0
    count = 0
    for section in raw.split(first_line)[1:]:
        if "Content-Disposition:" not in section:
            continue
        match = re.search(r'Content-Disposition: form-data; name="([^"]+)"', section)
        pos = section.find("\r\n\r\n")
        if not match or pos < 0:
            continue
        filename = match.group(1)
        target = (directory / filename).resolve()
        if not target.is_relative_to(directory.resolve()):
            raise ValueError("Unsafe filename in Worker source")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(section[pos + 4:].removesuffix("\r\n"), encoding="utf-8")
        count += 1
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--key-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    key_spec = json.loads(args.key_file.read_text(encoding="utf-8"))
    key = base64.b64decode(key_spec["key_base64"], validate=True)
    if len(key) != 32:
        raise ValueError("Invalid AES-256 key length")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Refusing to overwrite nonempty destination")
    args.output.mkdir(parents=True, exist_ok=True)
    all_objects = {}
    for part in (1, 2):
        file = ENCRYPTED / f"d1-catalog-2026-11-22-part{part}.aes256gcm.json"
        manifest = json.loads(file.read_text(encoding="utf-8"))
        raw = decode_archive(manifest, key, ROOT)
        data = json.loads(raw)
        if data.get("part") != part:
            raise ValueError("Backup part mismatch")
        if set(all_objects) & set(data["objects"]):
            raise ValueError("Duplicate snapshot keys")
        all_objects.update(data["objects"])
        print(f"Catalog part {part}: verified {len(data['objects'])} objects")
    for name, raw in all_objects.items():
        if not name.startswith("2026-11-22/d1/"):
            raise ValueError("Unexpected snapshot object path")
        target = (args.output / "kv-snapshot" / name).resolve()
        if not target.is_relative_to(args.output.resolve()):
            raise ValueError("Unsafe snapshot path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(raw, encoding="utf-8")
    sqlite_path = args.output / "catalog-2026-11-22.sqlite3"
    counts = restore_sqlite(all_objects, sqlite_path)
    with sqlite3.connect(sqlite_path) as db, (args.output / "catalog-2026-11-22.sql").open("w", encoding="utf-8") as fh:
        for line in db.iterdump():
            fh.write(line + "\n")
    for name in ["mntrees", "mntrees-admin", "mntrees-recovery-preview"]:
        file = ENCRYPTED / "workers" / f"{name}.aes256gcm.json"
        manifest = json.loads(file.read_text(encoding="utf-8"))
        clear = decode_archive(manifest, key, ROOT)
        print(f"{name}: verified {len(clear)} bytes, {extract_worker_parts(clear, args.output / 'workers' / name)} parts")
    summary = {"snapshot": "2026-11-22", "total_catalog_rows": sum(counts.values()), "tables": counts, "kv_objects": len(all_objects), "restored_sqlite": str(sqlite_path)}
    (args.output / "RESTORE_REPORT.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"RECOVERY VERIFIED: {summary['total_catalog_rows']} catalog rows, no FK violations, 3 Worker bundles")


if __name__ == "__main__":
    main()