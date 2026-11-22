#!/usr/bin/env python3
"""Browser-rendered menu discovery. Saves product-card evidence and source links for review.
Usage: python scripts/scan_rendered_menus.py [substring of retailer name]
Requires: pip install playwright && python -m playwright install chromium
Does not bypass access controls or automatically publish unverified prices.
"""
import asyncio, datetime, hashlib, json, re, sys
from pathlib import Path
from urllib.parse import urljoin
from strain_rules import match_strain, normalize_brand

TARGETS=Path("data/retailer_menu_scan_targets.json")
OUTPUT=Path("data/rendered_menu_candidates.json")
CATALOG=Path("data/auto_menu_offers.json")
HISTORY=Path("data/menu_price_history.json")
PRICE=re.compile(r"\$\s*(\d{1,4}(?:\.\d{2})?)")
WEIGHT=re.compile(r"\b(?:1/8|1/4|1/2)\s*oz\b|\b\d+(?:\.\d+)?\s*(?:g|gram|grams)\b",re.I)
EXCLUDE=re.compile(r"\b(?:gumm(?:y|ies)|edible|beverage|drink|vape|cartridge|tincture|topical|concentrate)\b",re.I)
CATEGORY=re.compile(r"\b(?:flower|pre[- ]?roll|joint|eighth|quarter)\b",re.I)


DUTCHIE_ID="6a3a88f076a17a4581275756"
DUTCHIE_HASH="91c683bfbce943059b6c958264577c1cff4a2623889a1c9db0be4a10ca7afd35"
DUTCHIE_TARGET="DIS-L25-000045-03-AUR"

async def fetch_dutchie(context,target,stamp):
 if target["id"]!=DUTCHIE_TARGET:return []
 output=[]
 for page in range(20):
  variables={"includeEnterpriseSpecials":False,"productsFilter":{"productIds":[],"dispensaryId":DUTCHIE_ID,"pricingType":"rec","strainTypes":[],"subcategories":[],"Status":"Active","types":["Flower"],"useCache":False,"isDefaultSort":True,"sortDirection":1,"bypassOnlineThresholds":False,"ignoreQuantityThresholds":False,"isKioskMenu":False,"removeProductsBelowOptionThresholds":True,"platformType":"ONLINE_MENU","preOrderType":None},"page":page,"perPage":100}
  params={"operationName":"FilteredProducts","variables":json.dumps(variables,separators=(",",":")),"extensions":json.dumps({"persistedQuery":{"version":1,"sha256Hash":DUTCHIE_HASH}},separators=(",",":"))}
  response=await context.request.get("https://dutchie.com/api-1/graphql",params=params,timeout=20000)
  if not response.ok:raise RuntimeError("Dutchie HTTP "+str(response.status))
  data=await response.json()
  if data.get("errors"):raise RuntimeError("Dutchie GraphQL error")
  block=data.get("data",{}).get("filteredProducts")
  if not isinstance(block,dict) or not isinstance(block.get("products"),list):raise RuntimeError("Missing Dutchie products")
  products=block["products"]
  for p in products:
   if p.get("type")!="Flower" or p.get("medicalOnly"):continue
   name=p.get("Name") or ""
   options=p.get("Options") or []
   prices=p.get("recPrices") or []
   if not name or len(options)!=len(prices):continue
   for weight,price in zip(options,prices):
    match=re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*g\s*",str(weight),re.I)
    if not match:continue
    grams=float(match.group(1))
    try:price=float(price)
    except (TypeError,ValueError):continue
    if not (0<grams<=28 and 1<=price<=500):continue
    ident="auto-dutchie-"+hashlib.sha256((target["id"]+"|"+str(p.get("id"))+"|"+str(grams)).encode()).hexdigest()[:18]
    strain=re.sub(r"^(?:pre[- ]?packed|flower)\s+","",name.split("|")[-1].strip(),flags=re.I)
    matched=match_strain(strain)
    if matched["match_status"]=="invalid":continue
    output.append({"strain_match_status":matched["match_status"],"strain_type":matched["strain_type"],"id":ident,"retailer":target["name"],"retailer_id":target["id"],"strain":matched["strain"],"product_name":name,"brand":normalize_brand(p.get("brandName") or ""),"category":"Flower","package_g":grams,"price":price,"city":"","state":"MN","address":"","url":target["url"],"checked_at":stamp,"source_method":"dutchie_filtered_products","stock_status":"not_verified","record_status":"automatically_extracted"})
  if len(products)<100:return output
 raise RuntimeError("Dutchie pagination safety limit")

async def scan(browser, target, semaphore):
 async with semaphore:
  result={"id":target["id"],"retailer":target["name"],"menu_url":target["url"],"scanned_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"error","products":[]}
  context=await browser.new_context(viewport={"width":1440,"height":900},locale="en-US")
  page=await context.new_page()
  try:
   response=await page.goto(target["url"],wait_until="domcontentloaded",timeout=35000)
   result["http_status"]=response.status if response else None
   await page.wait_for_timeout(4500)
   if target['id']==DUTCHIE_TARGET:
    try:
     result['direct_offers']=await fetch_dutchie(context,target,result['scanned_at'])
     result['dutchie_status']='success'
    except Exception as exc:
     result['dutchie_status']='error'
     result['dutchie_error']=str(exc)[:250]
   # Consent/age prompts are not automatically accepted; a blocked menu is reported for review.
   visible=await page.locator("body").inner_text(timeout=12000)
   if re.search(r"(verify your age|are you (?:21|over 21)|enter your date of birth)",visible[:3000],re.I):
    result["age_gate_detected"]=True
   # Collect visible product-like cards, including actual href where present.
   cards=await page.evaluate("""() => {
     const out=[], seen=new Set();
     const nodes=document.querySelectorAll('article,[class*="product-card"],[class*="productCard"],[data-testid*="product"],[class*="ProductCard"],[class*="product-item"],[class*="ProductItem"],[class*="menu-item"],[class*="MenuItem"],[data-product-id],[data-testid*="menu-item"]');
     for(const el of nodes){
       const text=(el.innerText||'').trim().replace(/\s+/g,' ');
       if(text.length<12||text.length>750||seen.has(text))continue;
       seen.add(text);
       const link=el.querySelector('a[href]');
       out.push({text,href:link?link.href:null});
     }
     return out.slice(0,1200);
   }""")
   # Also inspect links in visible rendered menus; avoid including unrelated navigation.
   for card in cards:
    body=card["text"]
    prices=PRICE.findall(body)
    if not prices or EXCLUDE.search(body):continue
    # Retain evidence even when flower/preroll categorization is uncertain.
    category="preroll" if re.search(r"pre[- ]?roll|\bjoint\b",body,re.I) else ("flower" if CATEGORY.search(body) or WEIGHT.search(body) else "needs_review")
    result["products"].append({"card_text":body[:650],"price_candidates":[float(p) for p in prices],"weight_candidates":WEIGHT.findall(body),"category_candidate":category,"product_url":card.get("href") or page.url,"source_menu_url":target["url"],"verified":False})
   result["status"]="dutchie_offers_found" if result.get("direct_offers") else ("candidates_found" if result["products"] else ("age_gate_or_dynamic_menu" if result.get("age_gate_detected") else "no_cards_extracted"))
   result["final_url"]=page.url
  except Exception as exc:
   result["error"]=str(exc)[:250]
  finally:
   await context.close()
  return result

async def main():
 from playwright.async_api import async_playwright
 targets=json.loads(TARGETS.read_text())
 selected_ids={x.strip() for x in __import__("os").environ.get("MNTREES_SCAN_TARGET_IDS","").split(",") if x.strip()}
 if selected_ids:targets=[t for t in targets if t["id"] in selected_ids]
 if len(sys.argv)>1:
  term=" ".join(sys.argv[1:]).lower()
  targets=[t for t in targets if term in t["name"].lower()]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  sem=asyncio.Semaphore(3)
  results=await asyncio.gather(*(scan(browser,t,sem) for t in targets))
  await browser.close()
 # Keep prior successful evidence on failures.
 previous={}
 if OUTPUT.exists():
  try:previous={r["id"]:r for r in json.loads(OUTPUT.read_text())["results"]}
  except (ValueError,KeyError,TypeError):pass
 for result in results:
  old=previous.get(result["id"])
  if old and old.get("products") and not result["products"]:
   result["last_successful_products"]=old["products"]
   result["last_successful_scan"]=old.get("scanned_at")
  previous[result["id"]]=result
 OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 OUTPUT.write_text(json.dumps({"total":len(previous),"results":list(previous.values())},indent=2)+"\n")
 # Publish only confidently parsed flower/preroll cards. Store durable price history.
 directory={x["id"]:x for x in json.loads(Path("data/retailer_locations.json").read_text())}
 def read_list(path):
  try:
   value=json.loads(path.read_text())
   return value if isinstance(value,list) else []
  except (OSError,ValueError):return []
 existing={x["id"]:x for x in read_list(CATALOG)}
 history=read_list(HISTORY)
 last={(x["id"],x["price"]) for x in history if "id" in x and "price" in x}
 for result in results:
  store=directory.get(result["id"],{})
  for offer in result.get("direct_offers",[]):
   offer["address"]=store.get("address","")
   ident=offer["id"]
   old=existing.get(ident)
   offer["first_seen"]=old.get("first_seen",old.get("checked_at")) if old else result["scanned_at"]
   existing[ident]=offer
   if (ident,offer["price"]) not in last:
    history.append({"id":ident,"retailer_id":result["id"],"price":offer["price"],"observed_at":result["scanned_at"],"source_url":offer["url"]})
    last.add((ident,offer["price"]))
  for item in result["products"]:
   body=item["card_text"]
   if item["category_candidate"]=="needs_review" or not item["price_candidates"]:continue
   if len(item["price_candidates"])!=1:continue
   weight=item["weight_candidates"]
   if len(weight)!=1:continue
   raw=weight[0].lower().replace(" ","")
   ounces={"1/8oz":3.5,"1/4oz":7.0,"1/2oz":14.0}
   try:grams=ounces[raw] if raw in ounces else float(re.search(r"\d+(?:\.\d+)?",raw).group())
   except (ValueError,AttributeError):continue
   if grams<=0 or grams>28:continue
   price=item["price_candidates"][0]
   if not 1<=price<=500:continue
   # The first line of the card must identify the product, not just a category.
   name=re.split(r"\s+(?:Indica|Sativa|Hybrid|THC|\$|\d+(?:\.\d+)?\s*(?:g|gram|oz))\b",body,maxsplit=1,flags=re.I)[0].strip()
   name=re.split(r"\s+\$\s*\d",name)[0].strip()
   if len(name)<4 or len(name)>115 or name.lower() in ("flower","pre-roll","preroll","shop flower"):continue
   if EXCLUDE.search(name) or re.search(r"\b(?:disposable\s+pen|all[- ]in[- ]one|aio\s+vape)\b",name,re.I):continue
   if re.fullmatch(r"(?:good\s+green|pre[- ]?rolls?\s*[·•]?)",name,re.I):continue
   if re.search(r"\\$\\s*\\d+(?:\\.\\d+)?\\s*off",name,re.I):continue
   if re.fullmatch(r"(?:sale\\s+)?0\\s+0\\s+in(?:\\s+cart)?",name,re.I):continue
   source=item["product_url"]
   if not isinstance(source,str) or not source.startswith("https://"):continue
   if re.search(r"/(?:vapes?|concentrates?|edibles?)(?:-|/)",source.lower()):continue
   if re.fullmatch(r"(?:hybrid|indica|sativa|flower|pre[- ]?roll|thc|cbd|small buds|premium flower)",name,re.I):continue
   category="Preroll" if item["category_candidate"]=="preroll" else "Flower"
   ident="auto-"+hashlib.sha256((result["id"]+"|"+source+"|"+name+"|"+str(grams)).encode()).hexdigest()[:18]
   matched=match_strain(name)
   if matched["match_status"]=="invalid":continue
   offer={"strain_match_status":matched["match_status"],"strain_type":matched["strain_type"],"id":ident,"retailer":result["retailer"],"retailer_id":result["id"],"strain":matched["strain"],"product_name":name,"brand":"","category":category,"package_g":grams,"price":price,"city":"","state":"MN","address":store.get("address",""),"url":source,"checked_at":result["scanned_at"],"source_method":"rendered_menu_card","stock_status":"not_verified","record_status":"automatically_extracted"}
   old=existing.get(ident)
   if old and old.get("price")==price:offer["first_seen"]=old.get("first_seen",old.get("checked_at"))
   else:offer["first_seen"]=old.get("first_seen",result["scanned_at"]) if old else result["scanned_at"]
   existing[ident]=offer
   if (ident,price) not in last:
    history.append({"id":ident,"retailer_id":result["id"],"price":price,"observed_at":result["scanned_at"],"source_url":source})
    last.add((ident,price))
 existing={k:v for k,v in existing.items() if not re.fullmatch(r"(?:hybrid|indica|sativa|flower|pre[- ]?roll|thc|cbd|small buds|premium flower)",v.get("strain",""),re.I)}
 CATALOG.write_text(json.dumps(list(existing.values()),indent=2)+"\n")
 HISTORY.write_text(json.dumps(history,indent=2)+"\n")
 print(json.dumps({"scanned":len(results),"with_candidates":sum(bool(r["products"]) for r in results),"candidate_cards":sum(len(r["products"]) for r in results),"published_offers":len(existing),"price_history_events":len(history)}))

if __name__=="__main__":asyncio.run(main())
