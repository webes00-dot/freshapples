#!/usr/bin/env python3
"""Review additional public cannabis sources without changing published MNtrees data.

Sammydentino: staged classifications and new-name candidates (historical, unlicensed repo).
Strain Database: narrow API discovery and a few named strain checks, respecting limits.
CannabisDB: metadata only; API is not currently released.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data/research"
MASTER=BASE/"strain_master_review_snapshot.json"
OUT=BASE/"additional_sources_review.json"
SAMMY="https://github.com/sammydentino/Cannabis-Strains"
SAMMY_RAW="https://raw.githubusercontent.com/sammydentino/Cannabis-Strains/master/"
DB="https://strain-database.com"
CANADA="https://www.cannabisdatabase.ca/cannabis_strains"
# Name-only spot checks, not bulk collection; stop after 4 checks.
TARGETS=["white-truffle","truffle-sundae","moonbow","zushi"]

def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").casefold())

def text(s,n=140):
    return " ".join(str(s or "").split())[:n]

def broad_type(s):
    s=str(s or "").casefold()
    if "hybrid" in s:return "hybrid"
    if "sativa" in s:return "sativa"
    if "indica" in s:return "indica"
    return ""

def load_remote(url):
    request=urllib.request.Request(url,headers={"User-Agent":"MNtrees strain research/1.0 (+https://github.com/webes00-dot/freshapples)","Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=35) as response:
        return json.load(response)

def run():
    rows=json.loads(MASTER.read_text(encoding="utf-8"))["records"]
    canonical={norm(r["strain"]):r for r in rows if r.get("strain")}
    aliases={}
    for r in rows:
        for a in re.split(r"[,;/|]",r.get("alias") or ""):
            a=norm(a)
            if a:aliases.setdefault(a,set()).add(norm(r["strain"]))
    report={
        "schema":"mntrees-supplemental-source-review-v1",
        "timestamp_utc":datetime.now(timezone.utc).isoformat(),
        "publication_status":"RESEARCH ONLY: not imported into public MNtrees data",
        "source_policy":"Do not auto-correct genetics, effects, classifications, or merge uncertain aliases.",
        "sammy":{"source":SAMMY,"dataset_date":"Last GitHub push 2020-07-18; historical","license":"No SPDX license declared; no public redistribution","conflicts":[],"missing_samples":[],"summary":{}},
        "strain_database":{"source":DB+"/blog/open-api-for-developers","policy":"No bulk scraping; documented 60 req/min general API. Contact provider for large exports and reuse terms.","checks":[]},
        "cannabisdb":{"source":CANADA,"listed_cultivars":120,"api_status":"API still under development; use as manually attributed reference only"}
    }
    s=report["sammy"];external={}
    for filename,race in (("Hybrids.json","hybrid"),("Indicas.json","indica"),("Sativas.json","sativa")):
        data=load_remote(SAMMY_RAW+filename)
        if not isinstance(data,list):raise ValueError(filename+" is not a list")
        for item in data:
            if not isinstance(item,dict):continue
            name=text(item.get("name"),120);key=norm(name)
            if not key:continue
            group=broad_type(item.get("race")) or race
            external.setdefault(key,{"name":name,"type":group,"files":[]})["files"].append(filename)
    counts={"unique_external":len(external),"matched":0,"unmatched":0,"conflicting_types":0,"ambiguous_aliases":0}
    for key,item in sorted(external.items()):
        match=canonical.get(key)
        match_type="Exact name"
        if not match and key in aliases:
            choices=aliases[key]
            if len(choices)!=1:
                counts["ambiguous_aliases"]+=1
                continue
            match=canonical.get(next(iter(choices)));match_type="Known alias"
        common={"source":SAMMY,"external_name":item["name"],"external_type":item["type"],"source_files":item["files"],"review_decision":"Needs review"}
        if not match:
            counts["unmatched"]+=1
            if len(s["missing_samples"])<200:
                s["missing_samples"].append({**common,"reason":"No exact name or explicit alias match"})
            continue
        counts["matched"]+=1
        actual=broad_type(match.get("classification"))
        if actual and item["type"] and actual!=item["type"]:
            counts["conflicting_types"]+=1
            if len(s["conflicts"])<350:
                s["conflicts"].append({**common,"canonical_strain":match["strain"],"mntrees_type":match.get("classification"),"match_type":match_type,"reason":"Historical broad-type conflict; requires owner review"})
    s["summary"]={**counts,"missing_samples_in_report":len(s["missing_samples"]),"conflicts_in_report":len(s["conflicts"])}
    db=report["strain_database"]
    try:
        result=load_remote(DB+"/api/strains?limit=2")
        db["discovery"]={"status":"accessible","response_shape":type(result).__name__,"top_level_keys":list(result)[:10] if isinstance(result,dict) else [],"sample_count":len(result) if isinstance(result,list) else None}
        for slug in TARGETS:
            try:
                item=load_remote(DB+"/api/strains/"+urllib.parse.quote(slug))
                record=item.get("data",item) if isinstance(item,dict) else {}
                if not isinstance(record,dict):record={}
                db["checks"].append({"slug":slug,"status":"accessible","name":text(record.get("name") or record.get("strain")),"type":text(record.get("type")),"breeder":text(record.get("breeder")) if isinstance(record.get("breeder"),str) else "", "quality_score":record.get("qualityScore"),"detail_url":DB+"/strains/"+slug,"note":"Targeted pilot only; parentage must be separately verified."})
            except Exception as e:
                db["checks"].append({"slug":slug,"status":"unavailable","reason":text(type(e).__name__+": "+str(e),100)})
    except Exception as e:
        db["discovery"]={"status":"unavailable","reason":text(type(e).__name__+": "+str(e),140)}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"sammy":s["summary"],"strain_database":db.get("discovery"),"strain_database_checks":len(db["checks"]),"cannabisdb":report["cannabisdb"]["api_status"]},indent=2))
if __name__=="__main__":
    run()
