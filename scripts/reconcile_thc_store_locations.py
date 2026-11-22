#!/usr/bin/env python3
"""Reconcile 367 THC menu observations to physical MNtrees store locations.

Use house number, street, city, and distinct business names. Conflicting addresses
are held, and no third-party price is promoted to the published catalog.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"collector/data/thc-catalog-audit/all_367_catalog_comparison.csv"
OUT=ROOT/"collector/data/thc-store-reconciled"

def canonical(text):
    x=str(text or "").lower()
    x=re.sub(r"\b(?:saint|st\.)\b","st",x)
    x=re.sub(r"[^a-z0-9]+"," ",x)
    return " ".join(x.split())
def city_compatible(city,address,name):
    if not city:return False
    c=canonical(city)
    body=canonical(str(address or "")+" "+str(name or ""))
    if re.search(r"\b"+re.escape(c)+r"\b",body):return True
    # Spelling errors such as Wilmar / Willmar, but never infer unrelated cities.
    parts=body.split()
    return len(c)>=5 and any(SequenceMatcher(None,c,p).ratio()>=.87 for p in parts)
def zip5(value):
    match=re.search(r"\b\d{5}\b",str(value or ""))
    return match.group() if match else ""
def address_essentials(text,city):
    x=canonical(text)
    tokens=x.split()
    # Preserve first street number, but ignore suite/unit identifiers.
    start=next((i for i,v in enumerate(tokens) if v.isdigit() and len(v)>=2),-1)
    if start<0:return "",set()
    number=tokens[start]
    t=tokens[start+1:]
    city_tokens=canonical(city).split()
    # Stop at locality, state or ZIP. Strip explicitly marked suite number.
    for i in range(len(t)):
        if t[i:i+len(city_tokens)]==city_tokens and city_tokens:
            t=t[:i];break
        if t[i]=="mn" or re.fullmatch(r"\d{5}",t[i]):
            t=t[:i];break
    if "suite" in t:t=t[:t.index("suite")]
    if "ste" in t:t=t[:t.index("ste")]
    replacements={"avenue":"ave","road":"rd","street":"st","drive":"dr","highway":"hwy",
      "boulevard":"blvd","place":"pl","lane":"ln","south":"s","north":"n",
      "east":"e","west":"w","parkway":"pkwy","memorial":"memorial"}
    street={replacements.get(v,v) for v in t if v not in {"unit","#","apt","floor"}}
    # Some store addresses concatenate the city name; filter locality tokens.
    street-=set(city_tokens)
    return number,street
def street_match(src,store,city):
    sn,st=address_essentials(src,city)
    mn,mt=address_essentials(store.get("address"),city)
    if not(sn and mn and sn==mn and st and mt):return False
    # Require substantial agreement; never use house number alone.
    overlap=len(st&mt)/max(len(st),len(mt))
    return overlap>=.67
def business_name_match(src,name):
    s=canonical(src)
    n=canonical(name)
    # Source may contain several aliases separated by commas.
    aliases=[canonical(a) for a in re.split(r"[,;|]",str(src or "")) if a.strip()]
    generic={"cannabis","co","company","dispensary","the","llc","store","recreational"}
    def distinctive(v):
        return [w for w in canonical(v).split() if w not in generic]
    target=set(distinctive(n))
    for alias in aliases+[s]:
        tokens=set(distinctive(alias))
        if tokens and tokens<=target:return True
        if len(alias)>=5 and alias in n:return True
    return False
def norm(v):return re.sub(r"[^a-z0-9]+","",str(v or "").lower())
def category(v):
    x=norm(v)
    if "preroll" in x or x=="preroll":return "preroll"
    if x in ("concentrate","concentrates"):return "concentrates"
    return "flower" if x=="flower" else x
def grams(x):
    try:return round(float(x),3)
    except (ValueError,TypeError):return None
def match_store(row,stores):
    source_addr=row.get("store_address","")
    city=row.get("city","")
    src_zip=zip5(row.get("store_zip")) or zip5(source_addr)
    # Owner policy: a uniquely identifiable store name and town is sufficient.
    # Address/ZIP disagreement is informational, not a blocker for this match.
    name_city=[
        store for store in stores
        if city_compatible(city,store.get("address"),store.get("name"))
        and business_name_match(row.get("store"),store.get("name"))
    ]
    if len(name_city)==1:
        return name_city[0],"unique_name_town_address_ignored",[(name_city[0],"unique_name_town_address_ignored")]
    if len(name_city)>1:
        # A duplicate research directory entry and a licensed entry describing
        # the same named business/town are not two separate storefronts.
        licensed=[store for store in name_city if not str(store["id"]).startswith("RESEARCH-")]
        if len(licensed)==1 and all(business_name_match(row.get("store"),store.get("name")) for store in name_city):
            return licensed[0],"unique_licensed_name_town_directory_duplicate",[(x,"name_town") for x in name_city]
        return None,"ambiguous_multiple_stores_same_name_town",[(x,"name_town") for x in name_city]
    hits=[]
    for store in stores:
        if not city_compatible(city,store.get("address"),store.get("name")):
            continue
        name_ok=business_name_match(row.get("store"),store.get("name"))
        street_ok=street_match(source_addr,store,city)
        store_zip=zip5(store.get("address"))
        zip_ok=bool(src_zip and store_zip and src_zip==store_zip)
        house_src,_=address_essentials(source_addr,city)
        house_dst,_=address_essentials(store.get("address"),city)
        if street_ok and (name_ok or zip_ok):
            level="street_name_city_match_zip_conflict" if src_zip and store_zip and not zip_ok else "street_name_city_match"
            hits.append((store,level))
        elif name_ok and house_src and house_src==house_dst and zip_ok:
            hits.append((store,"name_city_zip_house_match_street_review"))
    confirmed=[(s,how) for s,how in hits if how=="street_name_city_match"]
    if len(confirmed)==1:
        return confirmed[0][0],confirmed[0][1],hits
    if len(confirmed)>1:
        # Duplicate storefront directory entries at the same location:
        # prefer uniquely licensed, non-research entry when fully equivalent.
        licensed=[(s,h) for s,h in confirmed if not str(s["id"]).startswith("RESEARCH-")]
        addresses={norm(s.get("address")) for s,h in confirmed}
        if len(licensed)==1 and len(addresses)==1:
            return licensed[0][0],"licensed_store_duplicate_directory",hits
        return None,"multiple_directory_locations",hits
    if len(hits)==1:
        store,level=hits[0]
        return store,level,hits
    if len(hits)>1:return None,"multiple_possible_locations",hits
    return None,"no_location_match",hits

def main():
    with SOURCE.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=367:raise ValueError("Expected exact 367 reviewed rows")
    stores=json.loads((ROOT/"data/retailer_locations.json").read_text())
    offers=json.loads((ROOT/"dist/data/catalog.json").read_text())
    by_store=defaultdict(list)
    by_name=defaultdict(list)
    for offer in offers:
        if offer.get("retailer_id"):by_store[str(offer["retailer_id"])].append(offer)
        if offer.get("retailer"):by_name[norm(offer["retailer"])].append(offer)
    output=[];counts=Counter();unresolved_groups=Counter()
    for row in rows:
        # Existing definitive matches from previous audit retain their identity.
        if row["retailer_match_method"] in ("unique_location_license","unique_full_address"):
            store=next((s for s in stores if s["id"]==row["mntrees_retailer_id"]),None)
            method=row["retailer_match_method"]
        else:
            store,method,_=match_store(row,stores)
        status=""
        found=[]
        if store:
            current=by_store.get(store["id"],[]) + [
                o for o in by_name.get(norm(store["name"]),[]) if not o.get("retailer_id")]
            found=[o for o in current if (norm(o.get("brand"))==norm(row.get("brand"))
                and norm(o.get("strain"))==norm(row.get("strain_match_candidate"))
                and category(o.get("category"))==category(row.get("category"))
                and grams(o.get("package_g"))==grams(row.get("size_g_from_product_label")))]
            if method in ("unique_location_license","unique_full_address",
                          "street_name_city_match","licensed_store_duplicate_directory",
                          "unique_name_town_address_ignored","unique_licensed_name_town_directory_duplicate"):
                status="duplicate_on_site" if found else "new_sku_at_verified_location_pending_menu_price"
            else:
                status="location_identified_address_conflict_hold"
        else:
            status="no_confirmed_store_hold"
        counts[status]+=1
        if status in ("no_confirmed_store_hold","location_identified_address_conflict_hold"):
            unresolved_groups[(row.get("store"),row.get("city"),method)]+=1
        output.append({**row,"reconciled_status":status,
             "reconciled_store_id":store["id"] if store else "",
             "reconciled_store_name":store.get("name","") if store else "",
             "reconciled_store_address":store.get("address","") if store else "",
             "reconciled_store_match_method":method,
             "existing_sku_ids":"; ".join(str(o.get("id") or "") for o in found[:5]),
             "publish_eligible":"NO"})
    OUT.mkdir(parents=True,exist_ok=True)
    fields=list(output[0])
    with (OUT/"all_367_reconciled.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(output)
    for status,filename in [
        ("duplicate_on_site","duplicates.csv"),
        ("new_sku_at_verified_location_pending_menu_price","new_skus_to_verify.csv"),
        ("location_identified_address_conflict_hold","address_conflicts.csv"),
        ("no_confirmed_store_hold","unmatched_stores.csv")]:
        with (OUT/filename).open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            w.writerows(r for r in output if r["reconciled_status"]==status)
    report={"total":len(output),"catalog_offers":len(offers),"counts":dict(counts),
       "remaining_location_groups":[{"store":store,"city":city,"reason":reason,"observations":count}
          for (store,city,reason),count in unresolved_groups.most_common()],
       "definition":"Unique identifiable store name and town takes priority; ignore mismatched addresses and ZIPs when uniquely matched; ambiguous same-town names remain held",
       "published":0,
       "notes":["SKU matching uses brand/strain/category/exact grams at one physical retailer",
                "Historical THC API price is not proof of a current first-party menu listing",
                "Street and ZIP mismatches do not block a unique name-and-town store match; competing same-town storefronts remain held"]}
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Improved retailer reconciliation:",json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
