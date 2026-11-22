#!/usr/bin/env python3
"""Staged, non-publishing comparison of The Cannabis API and MNtrees Strain Master.

Does NOT change retail offers, genetics, classifications, or the website.
External dataset attribution: Piyush-Bhor/The_Cannabis_API (Kaggle-derived).
No large descriptions are copied; this is a review queue of factual metadata.
"""
import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/research/strain_master_review_snapshot.json"
OUT = ROOT / "data/research/cannabis_api_review.json"
SOURCE = "https://raw.githubusercontent.com/Piyush-Bhor/The_Cannabis_API/v2/cannabis.json"
SOURCE_LINK = "https://github.com/Piyush-Bhor/The_Cannabis_API/tree/v2"
MAX_NEW = 300
MAX_CONFLICT = 300
MAX_ENRICH = 350

def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

def type_group(value):
    s = str(value or "").casefold().strip()
    if "hybrid" in s:
        return "hybrid"
    if "indica" in s and "sativa" not in s:
        return "indica"
    if "sativa" in s and "indica" not in s:
        return "sativa"
    return ""

def string_value(value, maxlen=180):
    if isinstance(value, list):
        value = ", ".join(map(str, value))
    if not isinstance(value, (str, int, float)):
        return ""
    return " ".join(str(value).split())[:maxlen]

def main():
    master = json.loads(MASTER.read_text(encoding="utf-8"))["records"]
    known = {}
    aliases = {}
    for row in master:
        k = norm(row["strain"])
        if k:
            known.setdefault(k, []).append(row)
        for alias in re.split(r"[,;/|]", row.get("alias") or ""):
            a = norm(alias)
            if a:
                aliases.setdefault(a, []).append(row)
    req = urllib.request.Request(SOURCE, headers={"User-Agent":"MNtreesResearchComparison/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = json.load(response)
    assert isinstance(raw, list), "Expected Kaggle-style list in cannabis.json"
    new, conflicts, enriched, matched = [], [], [], 0
    seen_external = set()
    duplicate_external = 0
    ambiguous_alias = 0
    broad_type = 0
    unmatched_total = 0
    conflicts_total = 0
    enriched_total = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = string_value(item.get("Strain") or item.get("strain"), 100)
        typ = string_value(item.get("Type") or item.get("type"), 40)
        if not title:
            continue
        k = norm(title)
        if k in seen_external:
            duplicate_external += 1
            continue
        seen_external.add(k)
        matches = known.get(k) or aliases.get(k) or []
        matches = list({norm(x["strain"]):x for x in matches}.values())
        base = {"external_name":title,"external_type":typ,"effects":string_value(item.get("Effects") or item.get("effects")),"flavors":string_value(item.get("Flavor") or item.get("flavor")),"rating":item.get("Rating"),"source":SOURCE_LINK,"status":"Needs owner review"}
        if len(matches) > 1:
            ambiguous_alias += 1
            continue
        if not matches:
            unmatched_total += 1
            if len(new) < MAX_NEW:
                new.append({**base,"reason":"Not found in Strain Master by strict normalized name/known alias"})
            continue
        matched += 1
        rec = matches[0]
        group_current=type_group(rec.get("classification"))
        group_external=type_group(typ)
        # A broad Hybrid label should never override a vetted leaning subtype.
        conflict = bool(group_current and group_external and
            (group_current != group_external) and
            not (group_external == "hybrid" and "hybrid" in str(rec.get("classification","")).casefold()))
        reviewed={**base,"canonical_strain":rec["strain"],"mntrees_type":rec.get("classification",""),"matching":"Exact normalized name" if k in known else "Known alias"}
        if conflict:
            conflicts_total += 1
            if len(conflicts)<MAX_CONFLICT:
                conflicts.append({**reviewed,"reason":"Different broad indica/sativa/hybrid classification; NOT an automatic correction"})
        else:
            if group_external == "hybrid" and group_current == "hybrid":
                broad_type += 1
            if reviewed["effects"] or reviewed["flavors"]:
                enriched_total += 1
                if len(enriched) < MAX_ENRICH:
                    enriched.append({**reviewed,"reason":"Potential effects/flavor enrichment; historical user-report dataset, not lab verified"})
    data={
      "schema":"mntrees-external-cannabis-api-research-v1",
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "origin":SOURCE_LINK,
      "origin_dataset":"Kaggle cannabis-strains dataset via Piyush-Bhor The_Cannabis_API v2",
      "license_note":"README claims MIT but v2 source file LICENSE not confirmed. Research only, no public dataset redistribution until license checked.",
      "status":"STAGING ONLY: does not change published MNtrees data or editorial Strain Master",
      "matching":"Case-insensitive alphanumeric normalization, plus explicit existing alias field only; no fuzzy merging",
      "summary":{"master_records":len(master),"external_rows":len(raw),"external_distinct_names":len(seen_external),"duplicates_in_external":duplicate_external,"matched_master":matched,"new_name_candidates_total":unmatched_total,"type_conflicts_total":conflicts_total,"potential_effect_flavor_matches_total":enriched_total,"ambiguous_aliases":ambiguous_alias,"hybrid_broad_label_matches":broad_type,"new_name_candidates_in_queue":len(new),"type_conflicts_in_queue":len(conflicts),"effect_flavor_in_queue":len(enriched)},
      "type_conflicts":sorted(conflicts,key=lambda x:x["canonical_strain"].casefold()),
      "missing_strain_candidates":sorted(new,key=lambda x:x["external_name"].casefold()),
      "potential_effect_flavor_enrichment":sorted(enriched,key=lambda x:x["canonical_strain"].casefold())
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data["summary"],indent=2))
    print("Generated review-only file:",OUT)
if __name__=="__main__":
    main()
