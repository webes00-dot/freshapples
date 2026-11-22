#!/usr/bin/env python3
"""Audit current built MNtrees catalog; report safe correction opportunities."""
import collections
import json
import re
from pathlib import Path

records = json.loads(Path("dist/data/catalog.json").read_text())
counts = collections.Counter()
unmatched = []
blank = []
for x in records:
    name = str(x.get("strain") or "").strip()
    brand = str(x.get("brand") or "").strip()
    if not brand:
        blank.append(x)
    if x.get("strain_match_status") == "unmatched":
        unmatched.append(x)
    if not name or re.fullmatch(r"(?:sale\s+)?0\s+0\s+in(?:\s+cart)?", name, flags=re.I):
        counts["bad_names"] += 1
    if re.search(r"\b(?:flower|preroll|pre-roll|cart|vape)\b", name, flags=re.I):
        counts["format_noise_in_strain"] += 1
counts.update({"catalog": len(records), "unmatched": len(unmatched), "brand_blank": len(blank)})
# Stable source-ID review feed; the master sheet can import only flagged records.
import re as _re
noise = [x for x in records if _re.search(r"\b(?:flower|preroll|pre-roll|cart|vape)\b", str(x.get("strain") or ""), _re.I)]
print("ISSUE_KEYS_JSON", json.dumps({
    "missing_brand_ids": [str(x["id"]) for x in blank],
    "format_noise_ids": [str(x["id"]) for x in noise],
}, separators=(",", ":")))
print("CATALOG AUDIT", json.dumps(dict(counts), sort_keys=True))
for title, subset, key in [
    ("UNMATCHED TOP", unmatched, lambda x: str(x.get("strain") or "")),
    ("BRAND BLANK TOP", blank, lambda x: str(x.get("strain") or "")),
]:
    by = collections.Counter(key(x) for x in subset)
    print(title, json.dumps(by.most_common(35), ensure_ascii=False))
print("BRAND BLANK EXAMPLES", json.dumps([
    {"id": x.get("id"), "strain": x.get("strain"), "name": x.get("product_name"),
     "retailer": x.get("retailer"), "weight_g": x.get("package_g"), "category": x.get("category")}
    for x in blank[:30]], ensure_ascii=False))
