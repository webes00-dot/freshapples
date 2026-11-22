import csv, json, os, re, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"collector/data"/os.environ.get("THC_REVIEW_OUTPUT_DIR","thcminnesota-product-review")
CATEGORIES={"flower":"Flower","pre-rolls":"Pre-Rolls","concentrates":"Concentrates"}

def read(token,path,**params):
    url="https://thcminnesota.com/api/v1"+path+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json",
                 "User-Agent":"MNtrees-API-Review/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=50) as response:
                result=json.load(response)
            break
        except urllib.error.HTTPError as exc:
            # 403 may indicate an access/permission issue; do not hammer the endpoint.
            if exc.code not in (429,500,502,503,504) or attempt==3:
                raise
            time.sleep(2**attempt + 2)
        except (urllib.error.URLError,TimeoutError):
            if attempt==3:
                raise
            time.sleep(2**attempt + 2)
    if not isinstance(result,dict) or not isinstance(result.get("data"),list):
        raise ValueError("Unexpected response for "+path)
    return result


def explicit_grams(label):
    """Single explicit package quantity; never infer a multipack total."""
    label=str(label or "")
    total=re.search(r"(\d+(?:\.\d+)?|\.\d+)\s*(?:grams?|g)\s*(?:total|per package)\b",label,re.I)
    if total: return float(total.group(1)), "explicit_total"
    if re.search(r"\b\d+\s*(?:x|pk|pack)\s*\d",label,re.I):
        return None, "ambiguous_multipack"
    pieces=re.findall(r"(?<![\w.])(\d+(?:\.\d+)?|\.\d+)\s*(?:grams?|g)\b",label,re.I)
    sizes={float(x) for x in pieces if 0<float(x)<=56}
    if len(sizes)==1 and not re.search(r"\b\d+\s*(?:pk|pack|ct)\b",label,re.I):
        return sizes.pop(), "single_explicit_grams"
    return None, ("ambiguous" if sizes else "not_stated")


def fetch_products_by_id(token):
    products={}
    page_size=100
    first=read(token,"/products",limit=page_size,offset=0)
    total=first.get("total")
    if not isinstance(total,int) or total<0 or total>100000:
        raise ValueError("Unexpected products total")
    for offset in range(0,total,page_size):
        page=first if offset==0 else read(token,"/products",limit=page_size,offset=offset)
        for product in page["data"]:
            if product.get("id") is not None:
                products[str(product["id"])]=product
    if len(products)<total:
        raise ValueError("Incomplete product catalog; no unverified weight enrichment")
    return products

def main():
    token=os.getenv("THCMINNESOTA_API_KEY","").strip()
    if not token: raise SystemExit("Missing THCMINNESOTA_API_KEY")
    stores={}
    directory=read(token,"/dispensaries",limit=100,offset=0)
    total=directory.get("total",len(directory["data"]))
    for offset in range(0,total,100):
        page=directory if offset==0 else read(token,"/dispensaries",limit=100,offset=offset)
        for item in page["data"]:
            stores[str(item["id"])]=item
    if len(stores)<total:
        raise ValueError("Incomplete dispensary directory")
    products=fetch_products_by_id(token)
    master=json.loads((ROOT/"data/retailer_locations.json").read_text())
    licenses={str(v).upper():r["id"] for r in master for v in (r.get("id"),r.get("license_id")) if v}
    strain_master=json.loads((ROOT/"data/strain_master.json").read_text())
    canonical_by_name={re.sub(r"[^a-z0-9]+","",name.lower()):name
        for name in strain_master.get("canonical_strains",[])}
    def obvious_strain(title, brand):
        clean=lambda x:re.sub(r"[^a-z0-9]+","",str(x or "").lower())
        plain=clean(title)
        brand_key=clean(brand)
        if plain in canonical_by_name:
            return canonical_by_name[plain]
        if brand_key and plain.startswith(brand_key):
            return canonical_by_name.get(plain[len(brand_key):], "")
        if brand_key and plain.endswith(brand_key):
            return canonical_by_name.get(plain[:-len(brand_key)], "")
        return ""
    start_offset=int(os.getenv("THC_PRICE_START_OFFSET","0"))
    if start_offset<0 or start_offset%100:
        raise ValueError("Start offset must be nonnegative and multiple of 100")
    candidates=[]; metrics={}
    for slug,category_name in CATEGORIES.items():
        accepted=0; rejected=0; fetched=0
        for page in range(3): # bounded 300 observations per category
            page_data=read(token,"/pricing",category=slug,limit=100,offset=start_offset+page*100)
            rows=page_data["data"]; fetched+=len(rows)
            for row in rows:
                product=row.get("products") or {}
                brand=(product.get("brands") or {}).get("name")
                name=product.get("name")
                kind=(product.get("categories") or {}).get("name")
                store=stores.get(str(row.get("dispensary_id")))
                price=row.get("price")
                if kind!=category_name or not brand or not name or not store or not isinstance(price,(int,float)) or price<=0:
                    rejected+=1;continue
                license_id=str(store.get("license_number") or "").upper()
                product_record=products.get(str(row.get("product_id")), {})
                weight_label=product_record.get("weight_label") or ""
                weight_g, weight_evidence=explicit_grams(weight_label)
                strain=obvious_strain(name,brand)
                obvious=bool(weight_g and brand and strain)
                candidates.append({"category":slug,"brand":brand,"raw_title":name,
                    "strain_match_candidate":strain,
                    "triage":"obvious_three_fields_review" if obvious else "defer_not_obvious",
                    "triage_reason":("clear_size_brand_exact_strain" if obvious else
                        "missing_size" if not weight_g else "strain_not_unambiguous"),
                    "source_weight_label":weight_label,
                    "size_g_from_product_label":weight_g if weight_g else "",
                    "size_evidence":weight_evidence,
                    "size_review_status":"size_missing_or_ambiguous" if not weight_g else "explicit_label_verify_package",
                    "store":store.get("name"),"city":store.get("city"),
                    "store_address":store.get("address"),"store_zip":store.get("zip"),
                    "source_product_id":row.get("product_id"),
                    "source_dispensary_id":row.get("dispensary_id"),
                    "store_license":license_id,"mntrees_license_match":licenses.get(license_id,""),
                    "observed_price":price,"observed_date":row.get("scrape_date"),
                    "review_status":"pending","canonical_strain":"","confirmed_weight_g":""})
                accepted+=1
            if len(rows)<100:break
        metrics[slug]={"sampled_rows":fetched,"eligible_for_review":accepted,
                       "rejected_missing_brand_store_or_category":rejected,
                       "note":"Bounded first sample, not full historical coverage"}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"report.json").write_text(json.dumps({"checked_at":datetime.now(timezone.utc).isoformat(),
        "metrics":metrics,"price_start_offset":start_offset,"candidates":candidates,"publication_allowed":False},indent=2)+"\n")
    for suffix, subset in (
        ("obvious_candidates.csv", [x for x in candidates if x["triage"]=="obvious_three_fields_review"]),
        ("deferred.csv", [x for x in candidates if x["triage"]!="obvious_three_fields_review"])):
        if not subset:
            continue
        with (OUT/suffix).open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(subset[0]))
            writer.writeheader();writer.writerows(subset)
    if candidates:
        with (OUT/"candidates.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(candidates[0]))
            writer.writeheader();writer.writerows(candidates)
    from collections import Counter
    size_counts=Counter((x["category"],x["size_evidence"]) for x in candidates)
    print("Weight evidence:",json.dumps({str(k):v for k,v in size_counts.items()}))
    print("80/20 triage: obvious_three_fields_review",sum(x["triage"]=="obvious_three_fields_review" for x in candidates),
          "deferred",sum(x["triage"]!="obvious_three_fields_review" for x in candidates))
    print(json.dumps(metrics))
    print("Review only. No catalog, master sheet, or public changes.")

if __name__=="__main__":
    main()
