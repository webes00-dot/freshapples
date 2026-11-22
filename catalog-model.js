/* MNtrees shopper-facing normalization. Raw retailer offers are never rewritten. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;root.MNtreesCatalog=api})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
const simplify=s=>String(s||"").normalize("NFKD").toLowerCase().replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9]+/g," ").trim();
const CATEGORY={flower:"Flower",preroll:"Preroll",concentrate:"Concentrates"};
const numeric=n=>Number.isFinite(Number(n))&&Number(n)>0?Number(n):null;
const prerollForm=/\b(?:pre ?rolls?|joints?|blunts?|hash holes?)\b/;
const vapeForm=/\b(?:vapes?|vaporizers?|disposables?|cartridges?|carts?|aio)\b/;
const concentrateForm=/\b(?:concentrates?|extracts?|rosin|resin|wax|hash|shatter|badder|budder|diamonds|crumble|distillate|sauce|sugar|kief|dabs?|rso)\b/;
function typeOf(o){
 // Owner-confirmed: Kodjo's Dizgo Cherry Kush 1g listing is a preroll despite menu category.
 if(String(o.id||"")==="2e7da1544f83ac7cc0f1" || /kodjos\.dispensary\.shop\/rec\/flower\/pdp\/cherry-kush\//i.test(String(o.url||"")))return "Preroll";
 // Kodjo's MAC V2 five-pack is a 2.5g preroll multipack despite its Flower menu category.
 if(String(o.id||"")==="b922017567392166d488" || /kodjos\.dispensary\.shop\/rec\/flower\/pdp\/mac-v2-5pck-/i.test(String(o.url||"")))return "Preroll";
 const c=simplify(o.category);
 if(/\b(edible|edibles|gummy|gummies|chocolate|beverage|drink|tincture|topical|battery|batteries|accessory|accessories|charger|lighter|grinder|merchandise|gear)\b/.test(c))return null;
 if(prerollForm.test(c))return "Preroll";
 if(vapeForm.test(c))return "Vape";
 if(c.includes("flower")||c==="bud"||c==="buds")return "Flower";
 // Older imports sometimes used Concentrates for any product containing an extract.
 if(!o.reviewed_identity){
  const title=simplify(o.raw_scanned_product_name||o.product_name);
  if(prerollForm.test(title))return "Preroll";
  if(vapeForm.test(title))return "Vape";
 }
 return concentrateForm.test(c)?"Concentrates":null;
}
const slashPack=/(?:^|[\s|])(\d+(?:\.\d+)?|\.\d+)\s*g\s*\/\s*(\d{1,2})\s*(?:pk|packs?|ct)\b/i;
const fractionGram=/^([1-9]\d*)\s*\/\s*([1-9]\d*)\s*g(?:rams?)?\s+/i;
function packOf(o){
 const text=String(o.raw_scanned_product_name||o.product_name||o.strain||"");
 const actual=numeric(o.package_g);
 const reviewedCount=o.reviewed_identity && Number.isInteger(o.pack_count) && o.pack_count>1 ? o.pack_count : null;
 const mult=text.match(/\b(\d{1,2})\s*[xX×]\s*(0?\.\d+|\d+(?:\.\d+)?)\s*g\b/i)||text.match(/\b(\d{1,2})\s*(?:pk|pack|count|ct)\s*(?:of)?\s*[xX×]?\s*(0?\.\d+|\d+(?:\.\d+)?)\s*g\b/i);
 const reverse=text.match(/(?:^|[\s(])(\d+\.\d+|\.\d+|\d+)\s*g?\s*[xX×]\s*(\d{1,2})\b/i)||text.match(slashPack);
 const pack=text.match(/\b(\d{1,2})\s*(?:-?\s*pack|pk|ct)\b/i)||text.match(/\b(\d{1,2})\s*[xX×]\s*(?:pre.?rolls?|joints?)\b/i);
 const fraction=typeOf(o)==="Preroll"&&pack
  ? text.replace(/^(?:dizgo(?:\s+collective)?\s+)+/i,"").match(fractionGram) : null;
 let count=reviewedCount|| (mult?Number(mult[1]):reverse?Number(reverse[2]):pack?Number(pack[1]):null);
 let per=reviewedCount&&actual?actual/reviewedCount:mult?Number(mult[2]):reverse?Number(reverse[1]):fraction?Number(fraction[1])/Number(fraction[2]):null;
 const advertised=count&&per?Number((count*per).toFixed(3)):null;
 // Source-listed total is authoritative unless it conflicts with explicit pack math.
 const total=actual||advertised;
 const inconsistent=Boolean(actual&&advertised&&Math.abs(actual-advertised)>.08);
 if(inconsistent)count=null;
 const t=typeOf(o);
 // One-half gram is exactly 0.5g. 3.5g and 4g share eighth comparison bucket.
 const equivalent=t==="Flower"&&total!==null&&(Math.abs(total-3.5)<.01||Math.abs(total-4)<.01)?"eighth":t==="Flower"&&total!==null&&Math.abs(total-7)<.01?"quarter":total!==null?String(total):"unknown";
 const label=equivalent==="eighth"?"3.5 g":equivalent==="quarter"?"7 g":total!==null?format(total)+"g":"Weight not listed";
 const packLabel=count&&count>1?count+" pack"+(per?" × "+format(per)+"g":""):"";
 return {total,count:count&&count>1?count:null,per:inconsistent?null:per,equivalent,label,packLabel,inconsistent};
}
function format(n){return String(Number(n.toFixed(3)))}
function filterSize(o){
 const p=packOf(o),n=p.total;
 if(n===null)return "Weight not listed";
 // Filter-only buckets: keep source weight precise in each offer and card.
 if(n>=0.9-0.0001&&n<=1.05+0.0001)return "1 g";
 if(p.equivalent==="eighth")return "3.5 g";
 if(p.equivalent==="quarter")return "7 g";
 return format(n)+" g";
}
// Explicit known strain names override menu packaging and merchandising noise.
const KNOWN_STRAINS=["Zesty Parm","Cap Junky","Banana Push Pop","Bumper OG","Block Party","First Class Funk","Animal Scout","Brownie Scout","Trop Cherry","Blue Dream","Cherry Kush","Froot by the Foot","Hyperion F1","Purple Lemonade","Durban Z","Lemon Yacht Club","Toad Venom","Limesickle","Zour Zushi","Super Boof","Mochi Melon","Bourbon Berry x Whiskey Zulu"];
function knownStrain(o){
 const combined=[o.product_family,o.strain,o.product_name].filter(Boolean).join(" | ");
 const haystack=" "+simplify(combined)+" ";
 for(const name of KNOWN_STRAINS){
  const token=" "+simplify(name)+" ";
  if(haystack.includes(token))return name;
  if((" "+simplify(o.strain)+" ").includes(token)||(" "+simplify(o.product_name)+" ").includes(token))return name;
 }
 return "";
}
// Whitelisted retailer merchandising tokens. Source product_name is retained unchanged.
const NON_STRAIN_FIELD=/^(?:pre[- ]?packed|pre[- ]?packaged|prepack|prepacked|prepackaged|mixed|sativa(?:[- ]dom(?:inant)?)?|indica(?:[- ]dom(?:inant)?)?|hybrid|flower|concentrate|concentrates|vape|prerolls?|pre[- ]?rolls?|rosin|resin|disposable|cart(?:ridge)?|jar|chillum|\d+(?:\.\d+)?\s*(?:g|gm|grams?|ct|pk|packs?|oz)|\.?\d+\s*(?:g|gm|grams?|ct|pk|packs?|oz))$/i;
const FORMAT_FIELD=/\b(?:pre[- ]?roll[- ]?(?:ix|x)|flower\s*bag[- ]?ix|bag[- ]?ix|vape[- ]?ix|distillate|infused|disposable|cartridge|all[- ]in[- ]one|raw pre[- ]?rolls|(?:\d+)\s*vape[- ]?ix)\b/i;
const PREFIX_BRANDS=["Redwood County Weed Management","Campfire Cannabis","Float Cannabis Company","Float Cannabis","Classified Crops","Elevate Botanicals","Tasty Gems","Lakeside Cannabis","Lifted North","Good Green","Green Canopy","Dizgo Collective","Dope Cannabis","d'Ope Cannabis","Lake Leaf","Grasslandz","Minny Grown","Unbound","RYTHM","Rythm","Avion","Avio","FLÖR","Flor","Flör","Northpark","North Park","Northpark Cannabis Co","Redwood","Campfire","Float","Unwind Cultivation","Lakeside Cannabis","Lakeside Canna","Lakeside Cana","Laketown Farms","Laketown","Oma","Emerald Fire Farms","Emerald Farms","Native Care","SMIILE","Sappy Pappy","Verist Fields","Trailhead Cannabis Company","Trailhead Cannabis","Trailhead"];
function isMerchField(x){
 const s=String(x||"").trim();
 return !s||NON_STRAIN_FIELD.test(s)||FORMAT_FIELD.test(s)||slashPack.test(s)||/^\d+(?:\.\d+)?\s*(?:g|gm|gram|grams?|ct|pk|pack)\b/i.test(s)||/^\d+\s*[- ]?pack\b/i.test(s);
}
function structuredMenuTitle(o){
 const title=String(o.raw_scanned_product_name||o.product_name||o.strain||"").trim();
 const parts=title.split("|").map(part=>part.trim()).filter(Boolean);
 const brand=canonicalBrand(o.brand||o.brand_family);
 const first=parts[0]||"";
 const prefix=brand==="Float Cannabis"||/^float\s/i.test(first)
  ? /^(?:float(?:\s+cannabis(?:\s+co(?:mpany)?)?)?\s+)+/i
  : brand==="Dizgo Collective"?/^(?:dizgo(?:\s+collective)?\b\s*)+/i
  : brand==="Dogwalkers"?/^dog\s*walkers\s+/i
  : brand==="Unbound"?/^unbound\s+/i:null;
 const head=prefix?first.replace(prefix,"").trim():first;
 const isBrand=part=>Boolean(brand)&&canonicalBrand(part)===brand;
 if(parts.length===3&&slashPack.test(parts[1])&&/^(?:hybrid|indica|sativa)(?:[- ]dominant)?$/i.test(parts[2])
    &&!isMerchField(head)&&!isBrand(head)){
  return {strain:head,brand:brand||(/^float\s/i.test(first)?"Float Cannabis":"")};
 }
 if(parts.some(part=>/^mixed$/i.test(part))
    && parts.every(part=>isMerchField(part)||isBrand(part)||/^(?:vape\s+cartridge|live\s+rosin|hash\s+rosin)$/i.test(part)
       || (part===first&&brand==="Dizgo Collective"&&!head))){
  return {strain:"Mixed Strains",brand};
 }
 if(parts.length===1&&typeOf(o)==="Preroll"&&fractionGram.test(head)){
  const match=head.replace(fractionGram,"").match(/^(.+?)\s+(?:(?:hybrid|indica|sativa)\s+)?pre[- ]?rolls?\s+\d+\s*[- ]?pack$/i);
  if(match&&!isMerchField(match[1])){
   const strain=knownStrain({strain:match[1]})||(/^orion$/i.test(match[1])?"Orion":match[1]);
   return {strain,brand};
  }
 }
 return null;
}
function mnLoonIdentity(o){
 const inputs=[o.strain,o.product_name,o.raw_scanned_product_name];
 for(const value of inputs){
  const raw=String(value||"").trim();
  const match=raw.match(/^(?:mnl|mn\s*loon)\s+(.+)$/i);
  if(!match)continue;
  let name=match[1].replace(/\s*(?:1\s*\/\s*2\s*gram|0?\.5\s*(?:g|gram)?|half\s*gram)\s*$/i,"").trim().replace(/[.\s-]+$/,"");
  if(/^pinke\s+rozay$/i.test(name))name="Pink Rozay";
  if(/^nyc\s+diesel$/i.test(name))name="NYC Diesel";
  if(/^lemon\s+cherry\s+gelato$/i.test(name))name="Lemon Cherry Gelato";
  if(/^orange\s+creamsicle$/i.test(name))name="Orange Creamsicle";
  if(/^watermelon$/i.test(name))name="Watermelon";
  if(name)return {strain:name,brand:"MN Loon"};
 }
 return null;
}
function sappyPappyIdentity(o){
 // Sappy Pappy = Verist Fields concentrate product line, not cultivar.
 // Only exact named varieties from Verist's published menu qualify.
 const names={"dream berry":"Dream Berry","glacier valley sour":"Glacier Valley Sour",
              "sour luxx":"Sour Luxxe","sour luxxe":"Sour Luxxe"};
 for(const source of [o.strain,o.product_name,o.raw_scanned_product_name,o.product_family]){
  const raw=String(source||"").trim();
  if(!/\bsappy\s+pappy\b/i.test(raw))continue;
  const patterns=[
   /^(?:verist(?:\s+fields)?\s+){0,2}\|?\s*(?:cured\s+(?:live\s+)?resin\s*\|\s*)?sappy\s+pappy\s*\|\s*(.+?)(?:\s*\|\s*1\s*g)?$/i,
   /^(?:verist(?:\s+fields)?\s+)?sappy\s+pappy(?:\s+by\s+verist\s+fields)?\s+(.+?)(?:\s+1\s*g\s+cured\s+(?:live\s+)?resin)?$/i,
   /^(.+?)\s*[-|]\s*cured\s+(?:live\s+)?resin\s*[-|]\s*sappy\s+pappy(?:\s*[-|]\s*1\s*g)?$/i
  ];
  for(const re of patterns){
   const m=raw.match(re);
   if(m && names[m[1].trim().toLowerCase()])
    return {strain:names[m[1].trim().toLowerCase()],brand:"Verist Fields"};
  }
 }
 return null;
}
function trailheadTitleIdentity(o){
 for(const source of [o.strain,o.product_name,o.raw_scanned_product_name,o.product_family]){
  const raw=String(source||"").trim();
  const match=raw.match(/^(?:trailhead(?:\s+cannabis)?\s+)+(killer\s+cupcake|octane\s+mintz)(?:\s*(?:flower|3\.5\s*g|[-–().\s])*)$/i);
  if(match)return {strain:/killer/i.test(match[1])?"Killer Cupcake":"Octane Mintz",brand:"Trailhead Cannabis"};
 }
 return null;
}
function medusaPackIdentity(o){
 for(const source of [o.strain,o.product_name,o.raw_scanned_product_name,o.product_family]){
  const raw=String(source||"").trim();
  const match=raw.match(/^(?:(?:dizgo(?:\s+collective)?)\s+)?medusa(?:\s*\(?\s*\d+\s*[x×](?:\s*\d+(?:\.\d+)?\s*(?:g|gm|ct))?\s*\)?|\s+\d+\s*(?:pk|pack|pck|ct))?\s*$/i);
  if(match)return {strain:"Medusa",brand:/^dizgo/i.test(raw)?"Dizgo Collective":null};
 }
 return null;
}
function dizgoTitleIdentity(o){
 for(const source of [o.strain,o.product_name,o.raw_scanned_product_name,o.product_family]){
  const raw=String(source||"").trim().replace(/^(?:ON SALE|OFFER CONDITIONS APPLY)\s+/i,"");
  // Only these confirmed Dizgo cultivars: do not infer identity from "Dizgo" alone.
  const match=raw.match(/^(?:dizgo(?:\s+collective)?\s+)+(medusa|tri\s*cross)\b([\s\S]*)$/i);
  if(!match)continue;
  const remainder=match[2].trim();
  if(remainder && !/^(?:(?:\(?\d+\s*[x×]\s*)?(?:\d+(?:\.\d+)?\s*(?:g|gm|grams?)|(?:\d+\s*(?:pck|pack|pk|ct))|pre[-\s]?rolls?|flower|50\/50|[-–().\s])+)$/.test(remainder))continue;
  return {strain:/medusa/i.test(match[1])?"Medusa":"TriCross",brand:"Dizgo Collective"};
 }
 return null;
}
function reviewedTitleIdentity(o){
 const fields=[o.strain,o.product_name,o.product_family].map(v=>String(v||"").trim());
 for(const raw of fields){
  const title=raw.replace(/^(?:ON SALE|OFFER CONDITIONS APPLY|OFFER BUY \d+)\s+/i,"").trim();
  if(/^(?:cannabis\s+)?fog\s+dog(?:\s*\(\s*indica\s*\))?(?:\s+(?:flower|3\.5g))?$/i.test(title))return {strain:"Fog Dog"};
  if(/^dizgo(?:\s+collective)?\s+medusa(?:\s+(?:flower|prerolls?|pre-rolls?))?$/i.test(title))return {strain:"Medusa",brand:"Dizgo Collective"};
  if(/^dizgo(?:\s+collective)?\s+tri\s*cross(?:\s*(?:-|\s)\s*(?:\d+\s*(?:pck|pack|pk|ct)|flower|prerolls?|pre-rolls?|50\/50))*$/i.test(title))return {strain:"TriCross",brand:"Dizgo Collective"};
  if(/^emerald\s+(?:fire\s+)?farms\s+pineapple\s+burst(?:\s+\d+(?:\.\d+)?\s*g)?$/i.test(title))return {strain:"Pineapple Burst",brand:"Emerald Farms"};
  if(/^frodo\s+squeeze(?:\s+3\s*[x×])?$/i.test(title))return {strain:"Frodo Squeeze"};
  if(/^native\s+cuts\s+cheetah(?:\s+piss)?(?:\s+(?:flower|50\/50))?$/i.test(title))return {strain:"Cheetah Piss",brand:"Native Cuts"};
  if(/^native\s+cuts\s+mac(?:[-\s]?1)?(?:\s+(?:flower|50\/50)){0,2}$/i.test(title))return {strain:"MAC-1",brand:"Native Cuts"};
 }
 return null;
}
function ownerStrainBrandIdentity(o){
 const fields=[o.strain,o.product_name,o.product_family].map(v=>String(v||"").trim());
 for(const title of fields){
  if(/^(?:looner\s+)+(?:wild\s+grape)(?:\s+(?:flower|concentrate|preroll|pre-roll|\d+(?:\.\d+)?\s*g))*$/i.test(title))return {strain:"Wild Grape",brand:"Looner"};
  if(/^(?:(?:elevate|elevated)(?:\s+botanicals)?\s+)+strawberry\s+lemonade(?:\s+(?:flower|concentrate|preroll|pre-roll|\d+(?:\.\d+)?\s*g))*$/i.test(title))return {strain:"Strawberry Lemonade",brand:"Elevated Botanicals"};
 }
 return null;
}
function reviewedGranddaddy(name){
 const raw=String(name||"").trim();
 // Grandaddy, Grand Daddy, Granddaddy and GDP are owner-approved variants.
 // Strip only documented merchandising tokens, never change source weight.
 return /^(?:(?:grand\s*daddy|grand\s*addy|granddaddy|gdp)\s*(?:purp(?:le)?)?)(?:\s*(?:[-–|]\s*)?(?:flower|concentrates?|vapes?|carts?|cartridges?|prerolls?|pre-rolls?|distillate|indica|3\.5(?:\s*g)?|1(?:\.0)?\s*g))*$/i.test(raw)?"Granddaddy Purple":null;
}
function explicitProductIdentity(o){
 // Exact owner-approved catalog correction, including legacy deployed feed titles.
 // Match source ID first; the raw title is retained by the catalog builder.
 if(String(o.id||"")==="auto-a06095f26bd721f77a")return {strain:"Killer Cupcake",brand:"Trailhead Cannabis"};
 if(/dabney['’]?s cannabis/i.test(String(o.retailer||"")) &&
    /(?:^|\s)trailhead\s+reserve\s+killer\s+cupcake\b/i.test(String(o.strain||o.product_name||"")) &&
    Number(o.price)===40 && Number(o.package_g)===3.5)
   return {strain:"Killer Cupcake",brand:"Trailhead Cannabis"};
 // Owner-confirmed offer: D'Ope Cereal Milk live resin at Tranquil Gardens.
 // Match the displayed retailer, brand, generic title and price without relying
 // on optional category/product_type fields that may be absent in source data.
 if(/^live[-\s]?resin$/i.test(String(o.strain||o.product_name||"").trim())
   && /tranquil\s+gardens/i.test(String(o.retailer||""))
   && /d['’]?ope/i.test(String(o.brand||o.brand_family||""))
   && Number(o.price)===95)return {strain:"Cereal Milk",brand:"D'Ope"};

 // Retailer promotion disclaimer is not product identity.
 const promoTitle=String(o.strain||o.product_name||"").trim();
 if(/^offer\s+conditions\s+apply\b/i.test(promoTitle)){
  const name=promoTitle.replace(/^offer\s+conditions\s+apply\s*/i,"").trim();
  const identities=[
   [/^doctor\s+dabs\s+guerilla\s+stomper$/i,"Guerilla Stomper","Doctor Dabs"],
   [/^good\s+green\s+mystic\s+mint$/i,"Mystic Mint","Good Green"],
   [/^good\s+green\s+jack['’]?s\s+delight$/i,"Jack's Delight","Good Green"],
   [/^looner\s+looner\s+fr(?:oo|ui)t\s+by\s+the\s+foot$/i,"Froot by the Foot","Looner"],
   [/^unbound\s+unbound\s+wilfunk$/i,"Wilfunk","Unbound"],
   [/^verist\s+gush\s+kush$/i,"Gush Kush","Verist Fields"],
   [/^verist\s+mimosa\s+ice\s+flower$/i,"Mimosa Ice","Verist Fields"],
   [/^verist\s+swedish\s+og$/i,"Swedish OG","Verist Fields"],
   [/^verist\s+valley\s+frost\s+flower$/i,"Valley Frost","Verist Fields"]
  ];
  for(const [pattern,strain,brand] of identities)if(pattern.test(name))return {strain,brand};
 }

 const titleForIdentity=String(o.strain||o.product_name||"").trim();
 const mrBirch=titleForIdentity.match(/^mr\.?\s*birch\s+(?:(?:little\s+sticks?)\s*[-–]\s*)?(mimosa\s+ice|double\s+sour\s+grapes?|valley\s+frost)(?:\s+\d+(?:\.\d+)?\s*g)?$/i);
 if(mrBirch)return {strain:mrBirch[1].replace(/\b\w/g,c=>c.toUpperCase()),brand:"Mr. Birch"};
 const nativeCuts=titleForIdentity.match(/^native\s+cuts\s+(cheetah\s+piss|mac[- ]?1)$/i);
 if(nativeCuts)return {strain:/mac/i.test(nativeCuts[1])?"MAC-1":"Cheetah Piss",brand:"Native Cuts"};
 const minny=titleForIdentity.match(/^minny\s+grown\s+bumper\s+og$/i);
 if(minny)return {strain:"Bumper OG",brand:"Minny Grown"};

 // Purple Prince is the brand. Royal Oasis is the strain, regardless of title ordering.
 const purpleText=[o.strain,o.product_name,o.product_family].filter(Boolean).join(" | ");
 if(/\bpurple\s+prince\b/i.test(purpleText)&&/\broyal\s+oasis\b/i.test(purpleText))return {strain:"Royal Oasis",brand:"Purple Prince"};

 const productTitle=String(o.strain||o.product_name||"").trim();
 const doctor=productTitle.match(/^(?:doctor|doc|dr\.?)\s+dabs\s+(.+)$/i);
 if(doctor){
  const item=doctor[1].replace(/\s+3\.5\s+whole\s*sale\s*$/i,"").replace(/\s*\(3\.5g\)\s*$/i,"").trim();
  const strain=/^crypto\s+shifter$/i.test(item)?"Crypto Shifter":/^guerilla\s+stomper$/i.test(item)?"Guerilla Stomper":/^deli\s+style\s+popcorn$/i.test(item)?"Deli Style Popcorn":item;
  return {strain,brand:"Doctor Dabs"};
 }
 const dizgo=productTitle.match(/^dizgo(?:\s+collective)?\s+(.+)$/i);
 if(dizgo)return {strain:dizgo[1].trim(),brand:"Dizgo Collective"};
 const title=String(o.strain||o.product_name||"").trim();
 if(/^stashbox\s*x\s*loon\s+labs\s+live\s+resin\s+dirty\s+laundry$/i.test(title))return {strain:"Dirty Laundry",brand:"Stashbox x Loon Labs"};
 if(/^(?:waagbigwan|waabigwan)(?:\s+mashkiki)?\s+(.+)$/i.test(title)){
  const match=title.match(/^(?:waagbigwan|waabigwan)(?:\s+mashkiki)?\s+(.+)$/i);
  if(match && !/^mashkiki$/i.test(match[1]))return {strain:match[1],brand:"Waabigwan Mashkiki"};
 }

 // Verist is the brand; 5x is preroll packaging, not strain identity.
 const verist=title.match(/^verist(?:\s+fields)?\s+(double\s+sour\s+grapes?|gush\s+kush)(?:\s+5x)?$/i);
 if(verist)return {strain:verist[1].toLowerCase()==="gush kush"?"Gush Kush":"Double Sour Grape",brand:"Verist Fields"};
 const raw=[o.strain,o.product_name,o.product_family].filter(Boolean).join(" | ");
 const rules=[
  [/athos\s+diurnal\s+nect[oa]r\s*[-–]?\s*cured\s+live\s+resin/i,"Diurnal Nector","Athos"],
  [/aurora\s+cannabis\s+(?:llc\s+)?sour\s+diesel(?:\s*\(28g\))?/i,"Sour Diesel","Aurora Cannabis LLC"],
  [/aurora\s+cannabis\s+(?:llc\s+)?strawneapple(?:\s*\|\s*3\.5\s*g)?/i,"Strawneapple","Aurora"],
  [/bud\s+doctor\s+blueberry\s+diesel/i,"Blueberry Diesel","Bud Doctor"],
  [/bud\s+doctor\s+lemon\s+cherry\s+gelato/i,"Lemon Cherry Gelato","Bud Doctor"],
  [/bud\s+doctor\s+lemon\s+fresh/i,"Lemon Fresh","Bud Doctor"],
  [/cured\s+resin\s+sour\s+pebbles/i,"Sour Pebbles","D'Ope"]
 ];
 for(const [pattern,strain,brand] of rules)if(pattern.test(raw))return {strain,brand};
 return null;
}
function governmentOrangesVariant(o){
 const pattern=/\bgovernment\s+oranges?\b(?:\s+\(?(alpha|sour)\b)?/i;
 let variant=null;
 for(const title of [o.strain,o.product_name,o.product_family]){
  const match=String(title||"").match(pattern);
  if(!match)continue;
  if(o.product_variant==="Alpha" || o.product_variant==="Sour")return o.product_variant;
  if(match[1])return match[1].toLowerCase()==="alpha"?"Alpha":"Sour";
  variant="";
 }
 return variant;
}
function cleanStrain(o){
 // Source feeds sometimes place a quoted package size in the strain field.
 // Recover only an explicitly named cultivar from the full product title.
 const rawStrain=String(o.strain||'').trim();
 const weightOnly=/^[\s"'“”]*\.?\d+(?:\.\d+)?\s*(?:g|gm|grams?)[\s"'“”]*$/i;
 if(weightOnly.test(rawStrain)) {
  const fullTitle=[o.raw_scanned_product_name,o.product_name,o.product_family].find(value=>
   value && !weightOnly.test(String(value).trim()) && /[a-z]{2,}/i.test(String(value)));
  if(fullTitle) {
   const candidate=String(fullTitle).trim()
    .replace(/^[\s"'“”]+|[\s"'“”]+$/g,'')
    .replace(/\s*[|]\s*\.?\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*["'“”]*$/i,'')
    .replace(/\s+(?:live\s+rosin|hash\s+rosin|live\s+resin|cured\s+resin|concentrate|flower|pre[- ]?rolls?)\s*$/i,'')
    .replace(/^(?:FL[ÖO]R|FLOR)\s+/i,'').trim();
   if(candidate && !weightOnly.test(candidate) && !isMerchField(candidate))
    return candidate;
  }
  return 'Strain not specified';
 }
 const sappy=sappyPappyIdentity(o);
 if(sappy)return sappy.strain;
 const trailhead=trailheadTitleIdentity(o);
 if(trailhead)return trailhead.strain;
 const medusa=medusaPackIdentity(o);
 if(medusa)return medusa.strain;
 const dizgo=dizgoTitleIdentity(o);
 if(dizgo)return dizgo.strain;
 const skywalker=canonicalSkywalker(o.strain)||canonicalSkywalker(o.product_family)||canonicalSkywalker(o.product_name);
 if(skywalker)return skywalker;
 const reviewed=reviewedTitleIdentity(o);
 if(reviewed)return reviewed.strain;
 const owner=ownerStrainBrandIdentity(o);
 if(owner)return owner.strain;
 const granddaddy=[o.strain,o.product_name,o.product_family].map(reviewedGranddaddy).find(Boolean);
 if(granddaddy)return granddaddy;
 const mnLoon=mnLoonIdentity(o);
 if(mnLoon)return mnLoon.strain;
 if(governmentOrangesVariant(o)!==null)return "Government Oranges";
 if(o.reviewed_identity)return String(o.strain||"").trim();
 const structured=o.product_family_decision==="owner_confirmed_exact_listing"?null:structuredMenuTitle(o);
 if(structured)return structured.strain;
 const confirmed=explicitProductIdentity(o);
 if(confirmed && (confirmed.strain==="Cereal Milk" || confirmed.strain==="Dirty Laundry" || confirmed.strain==="Killer Cupcake"))return confirmed.strain;
 // Canonical strain aliases reviewed by the catalog owner.
 const original=String(o.strain||o.product_name||"").trim();
 // WM is an explicit abbreviation for the Waabigwan Mashkiki brand.
 if(/^wm\s+\S/i.test(String(o.strain||o.product_name||"").trim())){
  const title=String(o.strain||o.product_name||"").trim().replace(/^wm\s+/i,"");
  return cleanStrain({...o,strain:title,product_name:title,product_family:""});
 }

 // Verist Fields is the parent brand; Little Sticks and Mr. Birch are sub-brands.
 // A pack count or Flower label never forms part of the cultivar name.
 const veristTitle=String(o.strain||o.product_name||"").trim();
 const veristMatch=veristTitle.match(/^(?:verist(?:\s+fields)?\s+)(?:(?:mr\.?\s*birch|little\s+sticks)\s+)?(uffda\s+og|gush\s+kush|mimosa\s+ice|swedish\s+og|valley\s+frost)(?:\s+(?:flower|little\s+sticks|mr\.?\s*birch|\d+\s*x|3\.5\s*g))*$/i);
 if(veristMatch)return veristMatch[1].replace(/\b\w/g,c=>c.toUpperCase()).replace(/\bOg\b/g,"OG");
 // Owner-approved brand/strain separation for Valhalla and Verist product families.
 const ownerTitle=String(o.strain||o.product_name||o.product_family||"").trim();
 if(/^(?:(?:valhalla|vahalla)(?:\s+(?:select|cannabis))?\s+)?granola\s+funk(?:\s+(?:flower|3\.5\s*g))?$/i.test(ownerTitle))return "Granola Funk";
 if(/^(?:(?:verist(?:\s+fields)?|mr\.?\s*birch|little\s+sticks)\s+)?valley\s+frost(?:\s+(?:flower|3\.5\s*g|3\.5|\d+\s*x))?$/i.test(ownerTitle))return "Valley Frost";

 // Unbound is the product brand, not part of the cultivar name.
 // Remove one or more repeated brand prefixes from menu headings.
 const unboundTitle=String(o.strain||o.product_name||o.product_family||"").trim();
 if(/^unbound(?:\s+unbound)*\s+\S/i.test(unboundTitle)) {
  const cultivar=unboundTitle.replace(/^(?:unbound\s+)+/i,"").trim();
  if(cultivar && !/^(?:flower|preroll|pre-roll|vape|concentrate)$/i.test(cultivar))
   return cleanStrain({...o,strain:cultivar,product_name:cultivar,product_family:""});
 }

 // Apply the owner-approved Soap alias even when a source uses product_family
 // or supplies an already-computed displayStrain instead of strain.
 if([o.strain,o.product_name,o.product_family,o.displayStrain].some(v=>/^the\s+soap$/i.test(String(v||"").trim())))return "Soap";
 if(/^reserve\s+killer\s+cupcake(?:\s+(?:flower|3\.5\s*g))?$/i.test(original))return "Killer Cupcake";
 if(/^the\s+soap$/i.test(original))return "Soap";
 if(/^(?:trop|tropical|tropicana)\s+cherry$/i.test(original))return "Tropicana Cherry";
 if(/^stashbox\s*x\s*loon\s+labs\s+live\s+resin\s+dirty\s+laundry$/i.test(original))return "Dirty Laundry";

 // Owner-confirmed: Purple Prince is the brand, Royal Oasis the strain.
 if(/\bpurple\s+prince\s+royal\s+oasis\b/i.test([o.strain,o.product_name,o.product_family].join(" ")))return "Royal Oasis";
 const promo=explicitProductIdentity(o);
 if(promo && /^offer\s+conditions\s+apply\b/i.test(String(o.strain||o.product_name||"")))return promo.strain;
 // Promotion disclaimer is never part of the displayed strain name.
 const promotional=String(o.strain||o.product_name||"").trim();
 if(/^offer\s+conditions\s+apply\b/i.test(promotional)){
  const stripped=promotional.replace(/^offer\s+conditions\s+apply\b\s*[:\-–]?\s*/i,"").trim();
  if(stripped)return cleanStrain({...o,strain:stripped,product_name:stripped});
 }
 const sourceName=String(o.strain||o.product_name||"").trim();
 if(/^mendo\s+breath\s+auto$/i.test(sourceName))return "Mendo Breath";
 if(/^guava\s+3[.]?5(?:\s*g)?$/i.test(sourceName) && Number(o.package_g)===3.5 && /flower/i.test(String(o.category||"")))return "Guava";
 if(/^mendo\s+breath(?:e)?$/i.test(sourceName))return "Mendo Breath";
 if(/^mimosa\s+ice(?:\s+3\.5(?:\s*g)?)?$/i.test(sourceName))return "Mimosa Ice";
 if(/^night\s*hawk$/i.test(sourceName))return "Night Hawk";
 if(/^mike['’]?s\s+strawberry\s+lemonade$/i.test(sourceName))return "Strawberry Lemonade";

 // Owner-confirmed D'Ope concentrate at Tranquil Gardens: generic Live-Resin label.
 // Scope by retailer, brand, product form and price to avoid relabeling other resins.
 if(/^live[- ]resin$/i.test(String(o.strain||o.product_name||"").trim())
   && /tranquil gardens/i.test(String(o.retailer||""))
   && /^(?:d['’]?ope)$/i.test(String(o.brand||o.brand_family||"").trim())
   && /concentrat/i.test(String(o.category||o.product_type||""))
   && Number(o.price)===95)return "Cereal Milk";
 if(/^(?:little|big)\s+sticks?$/i.test(String(o.strain||o.product_name||"").trim()))return "Strain not specified";
 // Apostrophe and 2x preroll pack are not distinct strain identities.
 if(/^jacks?['\u2019]?\s*delight(?:\s+2\s*x)?$/i.test(String(o.strain||o.product_name||"").trim()))return "Jack's Delight";
 const purple=explicitProductIdentity(o);
 if(purple&&purple.brand==="Purple Prince")return "Royal Oasis";

 // Match a recognized strain before stripping trailing weights from branded titles.
 const earlyKnown=knownStrain(o);
 if(earlyKnown)return earlyKnown;
 // Owner-reviewed Minny Grown listing: strip the brand and weight, not the strain.
 if(/^minny\s+grown\s+zesty\s+parm(?:\s+3\.5\s*g)?$/i.test(String(o.strain||o.product_name||"").trim()))return "Zesty Parm";
 const rawTitle=String(o.strain||o.product_name||"").trim();
 // Strip package quantities from strain headings, not from the underlying offers.
 const withoutWeight=rawTitle.replace(/\s+(?:1\/8\s*)?\(?3\.5\s*g\)?\s*$/i,"").replace(/\s+1\/8\s*$/i,"").trim();
 if(/^frosted\s+run(?:ts|tz)$/i.test(withoutWeight))return "Frosted Runtz";
 if(/^night\s*hawk$/i.test(withoutWeight))return "Night Hawk";
 if(/^garlic\s+jam$/i.test(withoutWeight))return "Garlic Jam";
 if(/^fruit\s+blend\s+cured\s+resin$/i.test(withoutWeight))return "Strain not specified";
 if((withoutWeight!==rawTitle && !rawTitle.includes("|")) || /\brunts\b|\bfroot\b/i.test(rawTitle))return withoutWeight.replace(/\brunts\b/ig,"Runtz").replace(/\bfroot\b/ig,"Fruit").replace(/\borange\b$/i,"Oranges");
 if(/\borange\b$/i.test(rawTitle))return rawTitle.replace(/\borange\b$/i,"Oranges");

 if(/^double\s+sour\s+grapes?(?:\s+3\.5(?:\s*g)?)?$/i.test(String(o.strain||o.product_name||"").trim()))return "Double Sour Grape";
 const name=String(o.strain||o.product_name||"").trim();
 if(/^the\s+soap$/i.test(name))return "Soap";
 if(/^(?:trop|tropical|tropicana)\s+cherry$/i.test(name))return "Tropicana Cherry";
 if(/^valley\s+frost(?:\s+3\.5(?:\s*g)?)?$/i.test(name))return "Valley Frost";

 const combined=[o.strain,o.product_name,o.product_family].filter(Boolean).join(" | ");
 if(/purple\s+prince\s+royal\s+oasis/i.test(combined))return "Royal Oasis";
 if(/^purple\s+octane(?:\s+\d{1,2}(?:\.\d+)?\s*%\s*(?:thc)?)?$/i.test(String(o.strain||o.product_name||"").trim()))return "Purple Octane";
 // FLÖR's Pilot Light 2.0 is a naming variant of Pilot Light; preserve SKU sizes.
 if(/^pilot\s+light(?:\s+2\.0)?$/i.test(String(o.strain||o.product_name||'').trim()))return 'Pilot Light';
 const explicit=explicitProductIdentity(o);if(explicit)return explicit.strain;
 // Owner-confirmed Dabney's single preroll: &Shine is the brand, not the strain.
 if(/&shine\s+single\s+l['\u2019]orange/i.test([o.strain,o.product_name,o.product_family].join(" ")))return "L'Orange";
 // Source-specific confirmations: do not infer a strain from a shared AIO price or size.
 const id=String(o.id||"").trim();
 const source=String(o.url||"").toLowerCase();
 if(id==="85c9953bdfc18decf21a"||source.includes("/lemon-yacht-club-%7c-live-rosin-%7c-.5g-aio-vape/"))return "Lemon Yacht Club";
 if(id==="ce5e2c26bcff6c3239c3"||source.includes("/limesickle-%7c-live-rosin-%7c-.5g-aio-vape/"))return "Limesickle";
 // Explicit owner-reviewed display aliases: preserve original product names in source offers.
 const aliasCandidate=simplify([o.product_family,o.strain,o.product_name].filter(Boolean).join(" "));
 if(/\bfr(?:oo|ui)t by the foot\b/.test(aliasCandidate))return "Froot by the Foot";
 if(/\bdream\s*berry\b/.test(aliasCandidate))return "Dream Berry";
 if(/\bdulce\s+de\s+fresa\b/.test(aliasCandidate))return "Dulce de Fresa";
 if(/\bever\s*crisp\b/.test(aliasCandidate))return "Ever Crisp";
 if(/\bfranken\s*pine\b/.test(aliasCandidate))return "Franken Pine";
 if(/\bselect\s+granola\s+funk\b/.test(aliasCandidate))return "Granola Funk";
 if(/\bruntz\s+s1\b/.test(aliasCandidate))return "Runtz";
 if(/\bgastrona(?:u|un)t\b/.test(aliasCandidate))return "Gastronaut";
 if(/\bgorilla\s+glue\s*(?:#\s*)?4\b/.test(aliasCandidate))return "Gorilla Glue 4";
 // Retailer-specific spellings, format descriptors and source SKU suffixes.
 if(/\bgorilla\s+zkittl(?:es|ez)\b/.test(aliasCandidate))return "Gorilla Zkittlez";
 if(/\bgrand\s*daddy\s+purp(?:le)?\b/.test(aliasCandidate))return "Granddaddy Purple";
 if(/\bgummi\s*bears\b/.test(aliasCandidate))return "Gummibears";
 if(/\bgummy\s+gas\b/.test(aliasCandidate))return "Gummy Gas";
 if(/\bhalle\s+berry\b/.test(aliasCandidate))return "Halle Berry";
 if(/\bgastro\s+pop\b/.test(aliasCandidate))return "Gastro Pop";
 // RCWM menu titles sometimes embed brand, SKU weight and preroll count.
 if(/\bcap\s*junky\b/.test(aliasCandidate))return "Cap Junky";
 if(/\bsunset\s+tea\b/.test(aliasCandidate))return "Sunset Tea";
 if(/\bla\s+gueaga\b/.test(aliasCandidate))return "La Gueaga";
 if(/\bmendo\s+breath\s+auto\b/.test(aliasCandidate))return "Mendo Breath";
 if(/\bmendo\s+breath\b/.test(aliasCandidate))return "Mendo Breath";
 if(/\bhyperion(?:\s+f1)?\b/.test(aliasCandidate) && /\bhyperion\b/.test(aliasCandidate))return "Hyperion F1";
 if(/\bjelly\s+breath\b/.test(aliasCandidate))return "Jelly Breath";
 // Strain identities only: remove extract type and SKU packaging from titles.
 if(/\blemon\s+medusa\b/.test(aliasCandidate))return "Lemon Medusa";
 if(/\boctane\s+mintz\b/.test(aliasCandidate))return "Octane Mintz";
 if(/\bmac\s+v2\b/.test(aliasCandidate))return "MAC V2";
 if(/\btropic\s+fresa\b/.test(aliasCandidate))return "Tropic Fresa";
 // Owner-reviewed spacing and package suffixes.
 if(/\banimal\s+face\b/.test(aliasCandidate))return "Animal Face";
 if(/\bco\s+lime\s+ice\b/.test(aliasCandidate))return "Lime Ice";
 if(/\b(?:cultivation\s+)?campfire\s+cannabis\s+soap\b/.test(aliasCandidate))return "Soap";
 if(/^the\s+soap$/.test(simplify(o.product_family||o.strain||o.product_name)))return "Soap";
 if(/\bcherry\s+k\s+(?:3\s*(?:pck|pack|pk|ct)|three\s*pack)\b/.test(aliasCandidate))return "Cherry Kush";
 if(/\btri\s*cross\s+3\s*(?:pck|pack|pk|ct)\b/.test(aliasCandidate))return "TriCross";
 if(/\bnight\s*hawk\b/.test(aliasCandidate))return "Night Hawk";
 if(/\bplanet\s+of\s+the\s+grapes\b/.test(aliasCandidate))return "Planet of the Grapes";
 let raw=String(o.product_family||o.strain||o.product_name||"").trim();
 if(!raw)return "Strain not specified";
 // A deliberately reviewed, standalone family wins over the verbose source title.
 // A confirmed listing-level strain correction takes priority over tokens in the original menu title.
 if(o.product_family_decision==="owner_confirmed_exact_listing"&&o.product_family)return String(o.product_family).trim();
 if(/^tropical cherry$/i.test(raw))return "Tropical Cherry";
 if(/^mixed strains?$/i.test(raw))return "Mixed Strains";
 if(/^ak[- ]?47$/i.test(raw))return "AK-47";
 // The retailer prefixes 'Trailhead Cannabis' before the actual strain.
 // 'Cannabis' is never an independent strain for this producer.
 if(/^trailhead(?:\s+cannabis(?:\s+company)?)?(?:\s+trailhead)?\s+cannabis$/i.test(raw)||(/^cannabis$/i.test(raw)&&simplify(o.brand).startsWith("trailhead")))return "Strain not specified";
 if(simplify(o.brand).startsWith("trailhead") || /^trailhead(?:\s+cannabis)?\s+/i.test(raw)){
  const title=String(o.product_name||o.strain||raw);
  const first=title.split("|")[0].replace(/^(?:OFFER\s+CONDITIONS\s+APPLY\s+)?(?:Trailhead\s+)*(?:Trailhead\s+)?Cannabis(?:\s+Company)?\s+/i,"").replace(/^Trailhead\s+(?:Cannabis(?:\s+Company)?\s+)?/i,"").trim();
  if(first && !/^(?:cannabis|trailhead|pre[- ]?pack)/i.test(first) && !isMerchField(first)){
    raw=first;
  }
 }
 const recognized=knownStrain(o);

 if(recognized)return recognized;
 const parts=raw.split("|").map(s=>s.trim()).filter(Boolean);
 if(parts.length>1){
  const meaningful=parts.filter(s=>!isMerchField(s)&&simplify(s)!==simplify(o.brand)&&simplify(s)!==simplify(o.brand_family)&&!PREFIX_BRANDS.some(b=>simplify(s)===simplify(b)));
  if(meaningful.length){
   // Menu convention: [format] | [brand] | [category] | [size] | [strain] | [count].
   // A last meaningful field is a better candidate than a leading SKU descriptor.
   raw=meaningful[meaningful.length-1];
  }else if(parts.some(s=>/^mixed$/i.test(s)))return "Mixed Strains";
  else return "Strain not specified";
 }
 raw=raw.replace(/^(?:OFFER\s+(?:CONDITIONS\s+APPLY|BUY\s+\d+)\s+)+/i,"").trim();
 // Remove only complete brand prefixes, not a token that could be part of the strain.
 const prefixes=[o.brand,o.brand_family,...PREFIX_BRANDS].filter(Boolean).sort((a,b)=>b.length-a.length);
 for(let i=0;i<4;i++){
  const match=prefixes.find(b=>simplify(raw).startsWith(simplify(b)+" "));
  if(!match)break;
  raw=raw.slice(match.length).replace(/^[\s:|-]+/,"").trim();
 }
 // Trim leading packaging descriptors (for retailer formats lacking pipes).
 raw=raw.replace(/^(?:\d+(?:\.\d+)?\s*g\s+)?(?:flower\s*bag[- ]?ix|bag[- ]?ix|pre[- ]?roll[- ]?(?:ix|x)|live\s+resin\s+disposable[- ]?ix)\s*[-: ]*/i,"").trim();
 raw=raw.replace(/^(?:pre[- ]?rolls?|prerolls?)\s+/i,"").trim();
 // Packaging, size, classification and forms only at suffix boundaries.
 raw=raw.replace(/\s*(?:[-|]\s*)?(?:pre[- ]?packaged|pre[- ]?packed|prepacked|prepackaged)\b.*$/i,"");
 raw=raw.replace(/\s+(?:RCWM)\s*(?:\d+(?:\.\d+)?)?\s*$/i,"");
 raw=raw.replace(/\s+(?:\d+(?:\.\d+)?|\.?\d+)\s*(?:g|gm|grams?)\b.*$/i,"");
 raw=raw.replace(/\s+(?:\d+)\s*(?:ct|pk|packs?)\b.*$/i,"");
 raw=raw.replace(/\s+(?:hybrid|indica|sativa)(?:[- ]dominant)?\s*(?:\d+(?:\.\d+)?\s*g\b.*|(?:dispo|disposable|vape|flower)\b.*)?$/i,"");
 raw=raw.replace(/\s+(?:distillate|live\s+rosin|hash\s+rosin|live\s+resin|cured\s+resin|infused)\s+(?:infused\s+)?(?:pre[- ]?rolls?|prerolls?|all[- ]in[- ]one|vape|cartridge|cart|dispo(?:sable)?)\b.*$/i,"");
 raw=raw.replace(/\s+(?:pre[- ]?rolls?|prerolls?|dispo(?:sable)?|cartridge|cart|vape|flower|jar)\b.*$/i,"");
 raw=raw.replace(/(?:\s*[-|]\s*|\s+)(?:\d+\s*[- ]?pack|pre[- ]?rolls?)\b.*$/i,"");
 raw=raw.replace(/\s*[-|:]\s*$/,"").trim();
 if(recognized && (isMerchField(raw)||raw.length<3))return recognized;
 if(/^sunset sherbert$/i.test(raw))return "Sunset Sherbet";
 if(!raw||isMerchField(raw)||/^(?:510\s*vape[- ]?ix|pre[- ]?roll[- ]?x|bag[- ]?ix)$/i.test(raw))return "Strain not specified";
 return /^ak[- ]?47$/i.test(raw)?"AK-47":raw;
}
function canonicalBrand(name){
 const raw=String(name||"").trim(),key=simplify(raw);
 if(/^(?:feelin ?mn|feel n mn)$/.test(key))return "Feelin' MN";
 if(key==="popcorn"||key==="zips"||key==="zips cannabis")return "Zips";
 if(key==="avio supply co"||key==="avio supply company")return "Avio";
 if(key==="northpark cannabis co"||key==="northpark cannabis company")return "Northpark";
 if(key==="the greenest pastures")return "Greenest Pastures";
 if(key==="pot corn")return "Potcorn";
 if(key==="redwood weed management")return "Redwood County Weed Management";
 if(key==="trawa")return "Trawa";
 // Grasslands is currently listed separately from Grasslandz: don't infer a merger.

 if(/^(?:big dog|big dogs)$/.test(key))return "Big Dog";
 if(/^(?:grasslandz|grasslands|grass landz|grasslandz cannabis)$/.test(key))return "Grasslandz";
 if(/^(?:unbound|unbound cannabis|unbound cannabis co|unbound cannabis company)$/.test(key))return "Unbound";
 if(/^(?:dogwalkers|dog walkers)$/.test(key))return "Dogwalkers";
 if(/^(?:dabney|danbey)(?: ?s)?(?: cannabis(?: co| company)?)?$/.test(key))return "Dabney's Cannabis Co.";
 if(/^(?:valhalla|vahalla)(?: cannabis)?(?: co| company| collective| confections| farms)?$/.test(key))return "Valhalla Cannabis";
 if(/^aurora(?: ?s| cannabis(?: llc| mn dispensary)?)?$/.test(key))return "Aurora";
 if(/^d ope(?: cannabis)?$/.test(key))return "D'Ope";
 
 if(/^(?:verist|verist fields)$/.test(key))return "Verist Fields";
 if(/^(?:mr birch|mr\. birch)$/.test(key))return "Verist Fields";
 if(/^(?:little sticks|little stick|big sticks|big stick)$/.test(key))return "Verist Fields";
 if(/^(?:doctor|doc|dr) dabs$/.test(key))return "Doctor Dabs";
 if(key==="waagbigwan"||key==="waabigwan"||key==="wm"||key==="waabigwan mashkiki"||key==="waagbigwan mashkiki")return "Waabigwan Mashkiki";
 if(key==="mischief"||key==="mischief cannabis")return "Mischief Cannabis";
 if(/^(float|float canna|float cannabis|float cannabis co|float canna co|float cannabis company)$/.test(key))return "Float Cannabis";
 if(/^(dizgo|dizgo collective)$/.test(key))return "Dizgo Collective";
 if(["rythm","rhythm","rythym"].includes(key))return "RYTHM";
 if(/^(flor|flor fina|flor fina cannabis|flor by florfina|flor fina by flor)$/.test(key))return "FLÖR";
 if(/^(r d farms|r d pharms|r and d farms|r and d pharms|rd farms|rd pharms)$/.test(key))return "R & D Farms";
 if(/^(?:elevate|elevated)(?: botanicals)?$/.test(key))return "Elevated Botanicals";
 if(key==="mnl"||key==="mn loon"||key==="mnloon")return "MN Loon";
 if(key==="nativecare"||key==="native care")return "Native Care";
 if(key==="avio"||key==="avion")return "Avio";
 if(key==="marawanna")return "Marawanna";
 if(/^(trailhead|trailhead cannabis|trailhead cannabis company|trailhead farms)$/.test(key))return "Trailhead Cannabis";
 if(key==="campfire"||key==="campfire cannabis")return "Campfire Cannabis";
 if(key==="redwood"||key==="redwood county weed management")return "Redwood County Weed Management";
 if(key==="unwind cultivation"||key==="unwind")return "Unwind";
 if(/^(lakeside|lakeside canna|lakeside cannabis|lakeside cana)$/.test(key))return "Lakeside Cannabis";
 if(/^(campfire|campfire cannabis|campfire lake leaf|lake leaf|lakeleaf)$/.test(key))return "Campfire Cannabis";
 if(/^emerald(?: fire)? farms(?: .*)?$/.test(key))return "Emerald Farms";
 if(/^(laketown|laketown farms|oma)$/.test(key))return "Laketown Farms";
 if(key==="native care")return "Native Care";
 if(/^(northpark|north park|northpark cannabis co|northpark cannabis company|north park cannabis co|north park cannabis company)$/.test(key))return "Northpark";
 if(/^(smiile|smile|smiiles|smiles)$/.test(key))return "SMIILE";
 if(key==="sappy pappy"||key==="verist fields")return "Verist Fields";
 return raw;
}
function enriched(o){
 if(o.reviewed_identity)return {...o, displayStrain:cleanStrain(o), displayType:typeOf(o),
   pack:packOf(o), displayBrand:canonicalBrand(o.brand)||"Brand not confirmed",
   retailer:String(o.retailer||"").trim()};
 const pack=packOf(o),explicit=trailheadTitleIdentity(o)||medusaPackIdentity(o)||dizgoTitleIdentity(o)||reviewedTitleIdentity(o)||ownerStrainBrandIdentity(o)||mnLoonIdentity(o)||explicitProductIdentity(o),goodGreenMystic=/^good\s+green\s+(?:\(?2\s*[x×]\)?\s*)?mystic\s+mint\b/i.test(String(o.strain||o.product_name||"").trim()),goodGreenJacks=/^good\s+green\s+jacks?[\u0027\u2019]?\s*delight\b/i.test(String(o.strain||o.product_name||"").trim()),dirtyLaundryBranded=/stashbox\s*[x×]\s*loon\s+labs\s+live\s+resin\s+dirty\s+laundry/i.test([o.strain,o.product_name,o.product_family,o.displayStrain].join(" ")),valhallaBranded=/^(?:valhalla|vahalla)(?:\s+(?:select|cannabis))?\s+granola\s+funk\b/i.test(String(o.strain||o.product_name||"").trim()),veristTitle=String(o.strain||o.product_name||"").trim(),veristBranded=/^verist(?:\s+fields)?\s+/i.test(veristTitle),veristSubBrand=/\blittle\s+sticks\b/i.test(veristTitle)?"Little Sticks":/\bmr\.?\s*birch\b/i.test(veristTitle)?"Mr. Birch":"Verist Fields",wmBranded=/^wm\s+\S/i.test(String(o.strain||o.product_name||"").trim()),purplePrince=/purple\s+prince\s+royal\s+oasis/i.test([o.strain,o.product_name,o.product_family].join(" "));
 const brand=purplePrince?"Purple Prince":dirtyLaundryBranded?"Stashbox x Loon Labs":valhallaBranded?"Valhalla":veristBranded?veristSubBrand:wmBranded?"Waabigwan Mashkiki":explicit?(explicit.brand||o.brand||o.brand_family):(goodGreenMystic||goodGreenJacks)?"Good Green":(/&shine\s+single\s+l[\u0027\u2019]orange/i.test([o.strain,o.product_name,o.product_family].join(" "))?"&Shine":(o.brand||o.brand_family||(/^\s*marawanna\b/i.test(String(o.product_name||o.strain||""))?"Marawanna":(/^\s*angry apples\s*$/i.test(cleanStrain(o))?"Unbound":""))));
 return {...o,displayStrain:cleanStrain(o),displayType:typeOf(o),pack,
  displayBrand:canonicalBrand(brand)||structuredMenuTitle(o)?.brand||"Brand not confirmed",retailer:String(o.retailer||"").trim()};
}
function isValidDisplayStrain(s){
 // "Rewind" is a brand label, never a standalone cultivar heading.
 if(/^rewind$/i.test(String(s||'').trim()))return false;
 const name=String(s||"").trim();
 // A reversed producer name is not a verified cultivar. Keep the offer in
 // the catalog for editorial review but do not invent a public strain card.
 if(/^(?:farms\s+trailhead|trailhead\s+farms?)$/i.test(name))return false;
 if(/^pre[-\s]?pack(?:aged)?$/i.test(name))return false;
 if(/^(?:little|big)\s+sticks?$/i.test(name))return false;
 if(/^(?:sativa|indica|hybrid)\s+blend$/i.test(name)||/^fruit\s+blend\s+cured\s+resin$/i.test(name))return false;
 // Never present scraped shopping-cart counters as cannabis strains.
 if(/^(?:sale\s+)?0\s+0\s+in(?:\s+cart)?$/i.test(name))return false;
 if(/^(?:(?:\d+\s*[x×]\s*)?\.?\d+(?:\.\d+)?\s*g\s*(?:aio|all\s*in\s*one|(?:pre[- ]?rolls?|joints?)?)|\d+\s*[x×]\s*\d+(?:\.\d+)?\s*g)$/i.test(name))return false;
 if(/^[\s\"'“”]*\.?\d+(?:\.\d+)?\s*(?:g|gm|grams?)[\s\"'“”]*$/i.test(name))return false;
 return Boolean(name)&&name!=="Strain not specified"&&!/^\d+(?:\.\d+)?$/.test(name)&&!(/^(?:510\s*vape[- ]?ix|vape[- ]?ix|flower\s*bag[- ]?ix|pre[- ]?roll[- ]?[ix]|bag[- ]?ix|\d*\.?\d+\s*g\s*cart|(?:\d+(?:\.\d+)?\s*g\s*)?(?:cart|cartridge|disposable|flower|preroll|pre-roll))$/i.test(name));
}
// Multi-feed duplicates can have different source URLs (a research page, generic
// menu page, or product page). Deduplicate equivalent *retailer offers*, not URLs.
// Protect genuinely distinct SKUs: product form, exact weight, brand, price and
// explicit preparation/grade variants all participate in identity.
function offerVariant(o){
 const title=String(o.raw_scanned_product_name||o.product_name||"").toLowerCase();
 const variant=[];
 for(const [tag,pattern] of [
  ["infused",/\binfused\b/],["mini",/\bmini(?:s|\s+buds?)?\b/],
  ["premium",/\bpremium\b/],["popcorn",/\bpopcorn\b/],
  ["mixed-buds",/\bmixed\s+buds?\b/],["ground",/\bground\b/],
  ["shake",/\bshake\b/],["smalls",/\bsmalls?\b/],
  ["indoor",/\bindoor\b/],["outdoor",/\boutdoor\b/]
 ])if(pattern.test(title))variant.push(tag);
 return variant.join(",");
}
function offerIdentity(o){
 const store=String(o.retailer_id||"").trim()||simplify(o.retailer);
 const price=Number(o.price);
 const weight=o.pack.total;
 return [store,simplify(o.displayStrain),simplify(o.displayBrand),
   o.displayType,weight===null?"unknown":String(weight),
   Number.isFinite(price)?price.toFixed(2):"unknown",o.product_variant||"",offerVariant(o)].join("|");
}
function offerSourceQuality(o){
 const url=String(o.url||"").toLowerCase();
 const direct=/\/(?:pdp|product|products)\//.test(url);
 const dated=Boolean(o.checked_at);
 return Number(direct)*4+Number(dated)*2+Number(Boolean(o.raw_scanned_product_name));
}
function canonicalSkywalker(value){
 const raw=String(value||"").trim().replace(/\s+/g," ");
 // Only merchandising labels/spelling differ. Skywalker, Skywalker OG and
 // Skywalker Kush are separately approved in Strain Master.
 const m=raw.match(/^sky\s*walker(?:[\s-]+(og|kush))?(?:\s+(?:strain|flower|concentrates?|prerolls?|pre-rolls?|\d+(?:\.\d+)?\s*g))*$/i);
 if(!m)return null;
 return m[1]?("Skywalker "+m[1].toUpperCase().replace("KUSH","Kush")):"Skywalker";
}
function canonicalPublishedHeading(value){
 const name=String(value||"").trim().replace(/\s+/g," ");
 // Canonical strain names; Mr. Birch is a Verist packaging line and percentages are lab data.
 const birch=name.match(/^mr\.?\s*birch\s+(?:big\s+stick|little\s+sticks?)\s*[-–]?\s*(uptown\s+tart|double\s+sour\s+grapes?|valley\s+frost)(?:\s+pre[- ]?rolls?)?$/i);
 if(birch){const n=birch[1].toLowerCase();return n.startsWith("uptown")?"Uptown Tart":n.startsWith("double")?"Double Sour Grape":"Valley Frost";}
 if(/^purple\s+octane\s+\d+(?:\.\d+)?%$/i.test(name))return "Purple Octane";
 if(/^turtle\s+taffy\s+mn\s+roots$/i.test(name))return "Turtle Taffy";
 // Rewind is a brand, never a cultivar prefix. Resolve only explicit
 // owner-approved product titles, not arbitrary words after "Rewind".
 const rewind=name.match(/^rewind\s+(aloha\s+sugar|daily\s+grape|kanobi\s+sunset|killer\s+cupcake)$/i);
 if(rewind){
  const names={"aloha sugar":"Aloha Sugar","daily grape":"Daily Grape",
   "kanobi sunset":"Kanobi Sunset","killer cupcake":"Killer Cupcake"};
  return names[rewind[1].toLowerCase()];
 }
 // Highnorth is a storefront/offer label; "Discovery Pack" is packaging.
 // Never carry either into the canonical strain heading.
 const highnorth=name.match(/^highnorth\s+(turtle\s+taffy|white\s+widow)(?:\s+discovery\s+pack)?(?:\s*[-–]\s*\d+(?:\.\d+)?\s*g(?:\s+flower)?)?$/i);
 if(highnorth)return /^turtle/i.test(highnorth[1])?"Turtle Taffy":"White Widow";
 // Last-resort display safeguard for source titles with brand/package prefixes.
 // Torch Top is the cultivar; Mr. Birch is its Verist brand family.
 if(/^mr\.?\s*birch\s+(?:big\s+stick|little\s+sticks?)\s+torch\s+top(?:\s+pre[- ]?rolls?)?$/i.test(name))return "Torch Top";
 const aliases=[
  [/^cereal\s+milk\s+blend$/i,"Cereal Milk"],
  [/^cannabis\s+(turtle\s+taffy|fog\s+dog)$/i,null],
  [/^frodo\s+squeeze\s+3\s*[x×]$/i,"Frodo Squeeze"],
  [/^native\s+cuts\s+cheetah(?:\s+piss)?$/i,"Cheetah Piss"],
  [/^native\s+cuts\s+mac(?:[-\s]?1)?$/i,"MAC-1"],
  [/^emerald\s+(?:fire\s+)?farms\s+pineapple\s+burst$/i,"Pineapple Burst"],
  [/^trailhead(?:\s+cannabis)?\s+cherry\s+lady\s+slipper$/i,"Cherry Lady Slipper"],
  [/^(?:dizgo(?:\s+collective)?\s+)?medusa$/i,"Medusa"],
  [/^grand\s*daddy\s+purp(?:le)?$/i,"Granddaddy Purple"],
  [/^looner\s+(?:looner\s+)?wild\s+grape$/i,"Wild Grape"],
  [/^(?:elevate|elevated)(?:\s+botanicals)?\s+strawberry\s+lemonade$/i,"Strawberry Lemonade"],
  [/^sunset\s+sherbert$/i,"Sunset Sherbet"],
  [/^jacks?[\u0027\u2019]?\s*delight(?:\s+(?:2\s*[x×]|2\s*(?:pk|pack|ct)|pre[- ]?rolls?))?$/i,"Jack\u0027s Delight"],
  [/^(?:good\s+green\s+)?(?:\(?2\s*[x×]\)?\s*)?mystic\s+mint(?:\s*\(?2\s*[x×]\)?)?$/i,"Mystic Mint"],
  [/^(?:good\s+green\s+)?jacks?[\u0027\u2019]?\s*delight(?:\s+(?:\(?2\s*[x×]\)?|2\s*(?:pk|pack|ct)|pre[- ]?rolls?))?$/i,"Jack's Delight"],
  [/^(?:verist(?:\s+fields)?\s+)?gush\s+kush(?:\s+(?:little\s+sticks\s+)?\d+\s*[x×])?$/i,"Gush Kush"],
  [/^(?:verist(?:\s+fields)?\s+)?swedish\s+og(?:\s+(?:little\s+sticks\s+)?\d+\s*[x×])?$/i,"Swedish OG"],
  [/^(?:verist(?:\s+fields)?\s+)?mimosa\s+ice(?:\s+(?:little\s+sticks\s+)?\d+\s*[x×])?$/i,"Mimosa Ice"],
  [/^(?:verist(?:\s+fields)?\s+)?uffda\s+og(?:\s+(?:little\s+sticks\s+)?\d+\s*[x×])?$/i,"Uffda OG"],
  [/^stashbox\s*[x×]\s*loon\s+labs\s+live\s+resin\s+dirty\s+laundry$/i,"Dirty Laundry"],
  [/^government\s+oranges?$/i,"Government Oranges"],
  [/^night\s*hawk$/i,"Night Hawk"],
  [/^mendo\s+breath\s+auto$/i,"Mendo Breath Auto"],
  [/^mendo\s+breath(?:e)?$/i,"Mendo Breath"],
  [/^(?:the\s+)?soap$/i,"Soap"],
  [/^(?:reserve\s+)?killer\s+cupcake$/i,"Killer Cupcake"],
  [/^(?:verist(?:\s+fields)?\s+)?valley\s+frost(?:\s+(?:flower|3\.5(?:\s*g)?))?$/i,"Valley Frost"],
  [/^(?:valhalla|vahalla)(?:\s+select)?\s+granola\s+funk$/i,"Granola Funk"],
  [/^z[\s-]*cube$/i,"Z Cube"],
  [/^chem\s*dawg$/i,"Chemdawg"],
  [/^runtz\s+s1$/i,"Runtz"],
  [/^cherry\s+k(?:\s+3\s*(?:pck|pack|pk|ct))?$/i,"Cherry Kush"],
  [/^tri\s*cross(?:\s+3\s*(?:pck|pack|pk|ct))?$/i,"TriCross"]
 ];
 for(const [pattern,canonical] of aliases){const match=name.match(pattern);if(match)return canonical===null?match[1].replace(/\b\w/g,c=>c.toUpperCase()):canonical;}
 return name;
}

// Approved shopper-heading reconciliation: never turn product form, sub-brand,
// pack label, or merchandising grade into a separate cultivar card.
// Source titles and prices remain unchanged on each individual offer.
function reviewedPublicIdentity(o){
 // Exact Aurora retail product: brand/operator prefix is not the cultivar.
 if([o.strain,o.product_name,o.raw_scanned_product_name,o.master_strain].some(v=>
    /^aurora\s+cannabis\s+(?:llc\s+)?strawneapple(?:\s*\|\s*3\.5\s*g)?$/i.test(String(v||'').trim())))
    return {strain:"Strawneapple",brand:"Aurora"};

 const rawFields=[o.raw_scanned_product_name,o.product_name,o.strain,o.product_family,o.master_strain]
   .filter(Boolean).map(x=>String(x).trim());
 const exact=pattern=>rawFields.some(v=>pattern.test(v));
 // These are explicitly named source-title formats, never fuzzy matches.
 const rules=[
  [/^d['’]ope(?:\s+cannabis)?\s+anthos\s+blend\s*\|?\s*$/i,"Anthos Blend","D'Ope"],
  [/^(?:highnorth\s+)?turtle\s+taffy\s+discovery\s+pack$/i,"Turtle Taffy",null],
  [/^(?:highnorth\s+)?white\s+widow\s+discovery\s+pack$/i,"White Widow",null],
  [/^minny\s+grown(?:\s+minny\s+grown)?\s*(?:\|\s*flower\s*\|?\s*|\s+)franken\s*pine$/i,"Franken Pine","Minny Grown"],
  [/^minny\s+grown\s+sour\s+lemons$/i,"Sour Lemons","Minny Grown"],
  [/^mischief\s+premium\s+atlas\s+froot\s+by\s+the\s+foot$/i,"Froot by the Foot","Mischief Cannabis"],
  [/^mr\.?\s*birch\s+big\s*stick\s+torch\s+top$/i,"Torch Top","Verist Fields"],
  [/^north\s*park\s+510\s+vape\s+cart[- ]?ix\s*\|\s*gelato\s*#?\s*41$/i,"Gelato 41","Northpark"],
  [/^north\s*park\s+og\s+kush\s+cart$/i,"OG Kush","Northpark"],
  [/^r\s*&?\s*d\s+r\s*&?\s*d\s+pharms?\s*\|\s*black\s+maple\s*\|\s*pre[- ]?pack(?:aged)?$/i,"Black Maple 22","R & D Farms"],
  [/^rewind\s+aloha\s+sugar$/i,"Aloha Sugar","Rewind"],
  [/^rewind\s+daily\s+grape$/i,"Daily Grape","Rewind"],
  [/^rewind\s+kanobi\s+sunset$/i,"Kanobi Sunset","Rewind"],
  [/^rewind\s+killer\s+cupcake$/i,"Killer Cupcake","Rewind"],
  [/^turtle\s+taffy\s*[-–]\s*(?:2|8)\s*[- ]?pack$/i,"Turtle Taffy",null],
  [/^verist\s+fields\s+verist\s+fields\s*\|\s*cured\s+resin\s*\|\s*sappy\s+pappy\s*\|\s*dream\s+berry$/i,"Dream Berry","Verist Fields"],
  [/^verist\s+fields\s+verist\s+fields\s*\|\s*pre[- ]?packaged\s*\|\s*double\s+sour\s+grapes?$/i,"Double Sour Grape","Verist Fields"],
  [/^float\s+float\s*\|\s*pre[- ]?packaged\s*\|\s*gorilla\s+zkittl(?:es|ez)$/i,"Gorilla Zkittlez","Float Cannabis"],
  [/^float\s+magic\s+marker$/i,"Magic Marker","Float Cannabis"],
  [/^(?:&\s*)?shine\s+grand\s*daddy\s+purple$/i,"Granddaddy Purple","&Shine"],
  [/^trailhead\s+trailhead\s*\|\s*pre[- ]?packaged\s*\|\s*gastrona(?:u|un)t$/i,"Gastronaut","Trailhead Cannabis"]
 ];
 for(const [pattern,strain,brand] of rules){
  if(exact(pattern))return {strain,...(brand?{brand}:{})};
 }
 const values=[o.strain,o.product_name,o.raw_scanned_product_name,o.product_family,o.master_strain]
   .filter(Boolean).map(v=>String(v).trim());
 const matches=regex=>values.some(v=>regex.test(v));
 const named=(regex,name,brand)=>matches(regex)?{strain:name,...(brand?{brand}:{})}:null;
 // Prefer a directly recognizable product-title cultivar over a stale master heading.
 return named(/(?:^|\b)(?:3\/4\s*gram\s+)?l['’]orange\b/i,"L'Orange") && 
     matches(/(?:dogwalkers|big\s*dog|3\/4\s*gram)/i) ?
     {strain:"L'Orange",brand:"Dogwalkers"} :
   named(/(?:^|\b)gummi[-\s]?bear(?:s)?\s+live\s+rosin\b/i,"Gummibears","FLÖR") ||
   named(/^(?:highnorth\s+)?(?:turtle\s+taffy|white\s+widow)\s+discovery\s+pack$/i,
     matches(/white\s+widow/i)?"White Widow":"Turtle Taffy") ||
   named(/^(?:little\s*sticks?|little\s*stick\s+by\s+verist\s+fields)\s+(?:double\s+sour\s+grapes?|platinum\s+jesus)(?:\s+.*)?$/i,
     matches(/double\s+sour\s+grapes?/i)?"Double Sour Grape":"Platinum Jesus","Verist Fields") ||
   named(/^mr\.?\s*birch\s+(?:big\s+stick|little\s+stick)\s*[-–]?\s*(?:torch\s+top|swedish\s+og)(?:\s+.*)?$/i,
     matches(/torch\s+top/i)?"Torch Top":"Swedish OG","Verist Fields") ||
   named(/^(?:popcorn\s*[-–]\s*)?space\s+boogie(?:\s+.*)?$/i,"Space Boogie") ||
   named(/^purple\s+cereal\s+milk$/i,"Purple Milk") ||
   named(/^mendo\s+breath\s+auto$/i,"Mendo Breath") ||
   named(/^night\s*hawk$/i,"Night Hawk") ||
   named(/^pilot\s+light(?:\s+2\.0)?$/i,"Pilot Light") ||
   named(/^hyperion(?:\s+f1)?$/i,"Hyperion F1") ||
   null;
}

function groupOffers(input){
 // Shopper cards are grouped by canonical strain, across brands, forms and sizes.
 // Each offer retains its brand, price, category, package weight and source URL.
 // This keeps Big Dog and Dogwalkers Animal Face in one comparison card.
 const byKey=new Map();
 for(const original of input){
  // Rewind is a brand. Only the four owner-approved Rewind title identities
  // can be recovered from a Rewind-prefixed source strain/title. All others
  // remain review candidates rather than invented cultivar cards.
  const rewindRaw=String(original.strain||original.product_name||"").trim();
  if(/^rewind\b/i.test(rewindRaw) &&
     !/^rewind\s+(?:aloha\s+sugar|daily\s+grape|kanobi\s+sunset|killer\s+cupcake)$/i.test(rewindRaw))continue;
  // Exclude Elm Woods hemp flower from adult-use strain results.
  if(/\belm\s*woods?\b/i.test([original.strain,original.brand,original.brand_family,original.product_name,original.product_family].join(" ")))continue;
  const o=enriched(original);
  // Apply narrowly owner-approved source-title corrections BEFORE discarding
  // invalid-looking scraped fields such as "Pre-pack". The review parser may
  // recover a genuine master strain from the full product title.
  const earlyReviewed=reviewedPublicIdentity(original);
  if(earlyReviewed){
    o.displayStrain=earlyReviewed.strain;
    if(earlyReviewed.brand)o.displayBrand=earlyReviewed.brand;
  }
  if(!o.displayType||!isValidDisplayStrain(o.displayStrain))continue;
  const variant=governmentOrangesVariant(o);
  if(variant)o.product_variant=variant;
  // Apply owner-reviewed heading aliases at the final public grouping boundary.
  // Published offers carry the exact approved master name; client-side aliases
  // must not rewrite that canonical identity after the publication gate.
  // Publication boundary safety: never let an MNL/MnLooN brand prefix
  // become a cultivar heading, even if the published master_strain is stale.
  const confirmedMnLoon=mnLoonIdentity(original)||mnLoonIdentity(o);
  const confirmedReviewedTitle=reviewedTitleIdentity(original);
  o.displayStrain=confirmedMnLoon?.strain || confirmedReviewedTitle?.strain || canonicalSkywalker(o.displayStrain) || canonicalSkywalker(original.master_strain) || original.master_strain || canonicalPublishedHeading(o.displayStrain);
  if(confirmedMnLoon)o.displayBrand="MN Loon";
  if(/^(?:the\s+)?soap$/i.test(o.displayStrain))o.displayStrain="Soap";
  // Owner-requested comparison grouping: Skywalker, Skywalker OG and
  // Skywalker Kush share one shopper card, while the offer metadata retains
  // its exact master-approved cultivar variant for transparency.
  const skywalkerVariant=canonicalSkywalker(o.displayStrain);
  if(skywalkerVariant){
    if(skywalkerVariant!=="Skywalker")
      o.product_variant=[skywalkerVariant, o.product_variant].filter(Boolean).join(" · ");
    o.displayStrain="Skywalker";
  }
  const confirmedDizgo=dizgoTitleIdentity(original)||dizgoTitleIdentity(o);
  if(confirmedDizgo){
    o.displayStrain=confirmedDizgo.strain;
    o.displayBrand=confirmedDizgo.brand;
  }
  // Canonicalize after the master/title display fallback, otherwise a stale
  // master_strain can create a second Granddaddy Purple card.
  const granddaddy=reviewedGranddaddy(o.displayStrain) ||
    reviewedGranddaddy(original.master_strain) ||
    reviewedGranddaddy(original.strain) ||
    reviewedGranddaddy(original.product_name);
  if(granddaddy)o.displayStrain=granddaddy;
  if(/^(?:farms\s+trailhead|trailhead\s+farms?)$/i.test(o.displayStrain))continue;
  // Final boundary must apply the owner-approved cultivar/brand separation
  // even if a previously published master_strain still has a vendor prefix.
  const trailhead=trailheadTitleIdentity(original)||trailheadTitleIdentity(o);
  const medusa=medusaPackIdentity(original)||medusaPackIdentity(o);
  const titleIdentity=trailhead||medusa;
  if(titleIdentity){
    o.displayStrain=titleIdentity.strain;
    if(titleIdentity.brand)o.displayBrand=titleIdentity.brand;
  }
  // Strip classification and generic Cannabis prefix even when an old
  // published master_strain overrides the normalized product title.
  // FLÖR flower titles may contain an Indica prefix, weight, and redundant Flor label.
  // Normalize identity only; keep every original offer's price, weight, source, and brand.
  const fogDogFlor=[o.displayStrain,original.strain,original.product_name,original.master_strain]
    .some(value=>/^(?:indica\s+)?fl[öo]r\s+fog\s+dog\s*-\s*3\.5\s*-\s*flor\s+1\/8\s*oz$/i.test(String(value||'').trim()));
  if(fogDogFlor){o.displayStrain='Fog Dog';o.displayBrand='FLÖR';}
  const fogDogTitle=[o.displayStrain,original.strain,original.product_name,original.master_strain]
    .find(value=>/^(?:cannabis\s+)?fog\s+dog(?:\s*\(\s*indica\s*\))?$/i.test(String(value||"").trim()));
  if(fogDogTitle)o.displayStrain="Fog Dog";
  const approved=reviewedPublicIdentity(original) || reviewedPublicIdentity(o);
  if(approved){o.displayStrain=approved.strain;if(approved.brand)o.displayBrand=approved.brand;}
  // Canonicalize after master_strain fallback: legacy published names must
  // not create duplicate cards when an approved alias already exists.
  o.displayStrain=canonicalPublishedHeading(o.displayStrain);
  // Same Looner 1g disposable is labeled Sweet Orange/Sweet Oranges across retailers.
  if(/^sweet\s+oranges?$/i.test(o.displayStrain) &&
     /^(?:looner|looner cannabis)$/i.test(String(o.displayBrand||original.brand||"").trim()))
    o.displayStrain="Sweet Orange";
  // Unrecognized Highnorth-prefixed labels are not proven cultivars and
  // must not appear as invented strain cards. Exact known names are mapped
  // above, and source observations remain available for review.
  if(/^highnorth\b/i.test(o.displayStrain))continue;
  // Any Rewind prefix not matched to an approved cultivar stays out of the
  // shopper strain cards pending master/source reconciliation.
  if(/^rewind\b/i.test(o.displayStrain))continue;
  const key=simplify(o.displayStrain);
  if(!byKey.has(key))byKey.set(key,{strain:o.displayStrain,type:o.displayType,brand:o.displayBrand,offers:[]});
  const offers=byKey.get(key).offers;
  const identity=offerIdentity(o);
  const existing=offers.findIndex(x=>offerIdentity(x)===identity);
  if(existing!==-1){
   // Prefer product-specific URLs for shopper navigation. The other capture
   // remains in the raw source datasets for traceability.
   if(offerSourceQuality(o)>offerSourceQuality(offers[existing]))offers[existing]=o;
   continue;
  }
  offers.push(o);
 }
 for(const g of byKey.values()){
  const weights=[...new Set(g.offers.map(o=>o.pack.total))].sort((a,b)=>(a===null?Infinity:a)-(b===null?Infinity:b));
  g.size=weights.map(n=>n===null?"Weight not listed":format(n)+" g").join(" · ");
  const brands=[...new Set(g.offers.map(o=>o.displayBrand))];
  const types=[...new Set(g.offers.map(o=>o.displayType))];
  g.brand=brands.length===1?brands[0]:"Multiple brands";
  g.type=types.length===1?types[0]:"Mixed forms";
 }
 return [...byKey.values()].sort((a,b)=>a.strain.localeCompare(b.strain)||a.brand.localeCompare(b.brand)||a.type.localeCompare(b.type));
}
return {typeOf,packOf,filterSize,cleanStrain,canonicalBrand,enriched,groupOffers};
});
