#!/usr/bin/env python3
"""Audit all submitted retailer menu URLs; do not infer products from landing pages.\nRun on every updated storefront target list.\n"""
import concurrent.futures, datetime, json, re, urllib.error, urllib.request
from html import unescape
from pathlib import Path
targets=json.loads(Path("data/retailer_menu_scan_targets.json").read_text())
def scan(t):
    out=dict(t, scanned_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status="error",http_status=None,final_url=None,flower_mentions=0,preroll_mentions=0)
    try:
        req=urllib.request.Request(t["url"],headers={"User-Agent":"Mozilla/5.0 (compatible; MNtreesMenuAudit/1.0)","Accept":"text/html,application/json"})
        with urllib.request.urlopen(req,timeout=16) as r:
            data=r.read(450000).decode("utf-8","replace")
            out.update(http_status=r.status,final_url=r.url,status="reachable")
            # Inspect JSON-LD structured products; retain only flower and preroll candidates for review.
            candidates=[]
            for raw in re.findall(r'<script[^>]*type=["\x27]application/ld[+]json["\x27][^>]*>(.*?)</script>',data,re.I|re.S):
                try:
                    parsed=json.loads(unescape(raw))
                    stack=parsed if isinstance(parsed,list) else [parsed]
                    while stack:
                        item=stack.pop()
                        if isinstance(item,list):stack.extend(item);continue
                        if not isinstance(item,dict):continue
                        stack.extend(v for k,v in item.items() if k in ("@graph","itemListElement") and isinstance(v,(list,dict)))
                        typ=item.get("@type",[])
                        if isinstance(typ,str):typ=[typ]
                        if "Product" not in typ:continue
                        name=str(item.get("name","")).strip()
                        if not name or not re.search(r'flower|pre[- ]?roll|[0-9]+(?:[.][0-9]+)?[ ]*g',name,re.I):continue
                        if re.search(r'edible|gummy|gummies|beverage|drink|chocolate|vape|cartridge|tincture',name,re.I):continue
                        offer=item.get("offers",{})
                        if isinstance(offer,list):offer=offer[0] if offer else {}
                        candidates.append({"name":name,"price":offer.get("price") if isinstance(offer,dict) else None,"url":item.get("url") or r.url})
                except (ValueError,TypeError):pass
            out["structured_product_candidates"]=candidates[:100]
            out["flower_mentions"]=len(re.findall(r"\bflower\b",data,re.I))
            out["preroll_mentions"]=len(re.findall(r"pre[- ]?roll",data,re.I))
            if not (out["flower_mentions"] or out["preroll_mentions"] or out["structured_product_candidates"]):out["status"]="reachable_no_product_evidence"
    except urllib.error.HTTPError as e:
        out.update(http_status=e.code,status="http_error")
    except Exception as e:
        out["error"]=str(e)[:180]
    return out
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results=list(pool.map(scan,targets))
Path("data/retailer_menu_scan_report.json").write_text(json.dumps({"total":len(results),"results":results},indent=2)+"\n")
from collections import Counter
print("Menu scan:",dict(Counter(r["status"] for r in results)))
