const assert=require("node:assert/strict");
const {typeOf,packOf,cleanStrain,canonicalBrand,groupOffers,enriched}=require("../catalog-model.js");
assert.equal(typeOf({category:"Flower"}),"Flower");
assert.equal(typeOf({category:"Infused Preroll"}),"Preroll");
assert.equal(typeOf({category:"Concentrates",product_name:"Live Rosin Infused Pre-Roll"}),"Preroll");
assert.equal(typeOf({category:"Concentrates",product_name:"Hash Hole 2.5g"}),"Preroll");
assert.equal(typeOf({category:"Concentrates",product_name:"Pink Runtz Live Resin Disposable 1g"}),"Vape");
assert.equal(typeOf({category:"Concentrates",product_name:"Pink Runtz Live Resin 1g"}),"Concentrates");
assert.equal(typeOf({category:"Unknown",product_name:"Pink Runtz"}),null);
assert.equal(typeOf({category:"Concentrates",product_name:"Ambiguous Joint listing",reviewed_identity:true}),"Concentrates");
for(const c of ["Concentrate","Resin","Rosin"])assert.equal(typeOf({category:c}),"Concentrates");
for(const c of ["Vape","Disposable","Cartridge"])assert.equal(typeOf({category:c}),"Vape");
assert.equal(typeOf({category:"Battery"}),null);
assert.equal(typeOf({category:"Edible"}),null);
assert.equal(typeOf({category:"Gummies"}),null);
assert.equal(canonicalBrand("Float Canna Co"),"Float Cannabis");
assert.equal(canonicalBrand("Float Cannabis Company"),"Float Cannabis");
assert.equal(canonicalBrand("Dizgo"),"Dizgo Collective");
assert.equal(canonicalBrand("Dizgo Collective"),"Dizgo Collective");
for(const name of ["Trailhead","Trailhead Cannabis","Trailhead Cannabis Company"]){
 assert.equal(canonicalBrand(name),"Trailhead Cannabis");
}
for(const raw of ["Trailhead Killer Cupcake Flower","Trailhead Cannabis Octane Mintz 3.5g"]){
 assert.ok(!/^trailhead/i.test(cleanStrain({strain:raw,product_name:raw,category:"Flower"})), "Brand prefix left in cultivar: "+raw);
}
const trailheadReviewed=groupOffers([{id:"auto-a06095f26bd721f77a",retailer:"Dabney's Cannabis Co.",strain:"Trailhead Reserve Killer Cupcake",product_name:"Trailhead Reserve Killer Cupcake",brand:"Trailhead",category:"Flower",price:40,package_g:3.5}]);
assert.equal(trailheadReviewed[0].strain,"Killer Cupcake");
assert.equal(trailheadReviewed[0].offers[0].displayBrand,"Trailhead Cannabis");
 for(const variant of ["Flor","FLOR","Flör","FLÖR"])assert.equal(canonicalBrand(variant),"FLÖR");
for(const variant of ["Campfire","Campfire Cannabis"])assert.equal(canonicalBrand(variant),"Campfire Cannabis");
for(const variant of ["Redwood","Redwood County Weed Management"])assert.equal(canonicalBrand(variant),"Redwood County Weed Management");
assert.equal(groupOffers([
 {strain:"Cap Junky",brand:"Campfire",category:"Flower",package_g:3.5,retailer:"A",price:35},
 {strain:"Cap Junky",brand:"Campfire Cannabis",category:"Flower",package_g:3.5,retailer:"B",price:38}
]).length,1);
assert.equal(groupOffers([
 {strain:"Block Party",brand:"Redwood",category:"Flower",package_g:3.5,retailer:"A",price:35},
 {strain:"Block Party",brand:"Redwood County Weed Management",category:"Flower",package_g:3.5,retailer:"B",price:38}
]).length,1);
assert.equal(canonicalBrand("Lakeside Canna"),"Lakeside Cannabis");
assert.equal(canonicalBrand("Lakeside Cana"),"Lakeside Cannabis");
assert.equal(canonicalBrand("Lakeside Cannabis"),"Lakeside Cannabis");
assert.equal(canonicalBrand("Lake Leaf"),"Campfire Cannabis");
assert.equal(canonicalBrand("Campfire / Lake Leaf"),"Campfire Cannabis");
assert.equal(canonicalBrand("Emerald Fire Farms"),"Emerald Farms");
assert.equal(canonicalBrand("Emerald Farms"),"Emerald Farms");
assert.equal(canonicalBrand("Laketown"),"Laketown Farms");
assert.equal(canonicalBrand("Laketown Farms"),"Laketown Farms");
assert.equal(canonicalBrand("Oma"),"Laketown Farms");
assert.equal(canonicalBrand("Native care"),"Native Care");
assert.equal(canonicalBrand("Native Care"),"Native Care");
assert.equal(canonicalBrand("North Park"),"Northpark");
assert.equal(canonicalBrand("Northpark Cannabis Co"),"Northpark");
assert.equal(canonicalBrand("Northpark"),"Northpark");
assert.equal(canonicalBrand("sMIILE"),"SMIILE");
assert.equal(canonicalBrand("SMIILE"),"SMIILE");
assert.equal(canonicalBrand("Sappy Pappy"),"Verist Fields");
for(const [raw,expected] of [
 ["Verist Fields Verist Fields | Cured Resin | Sappy Pappy | Dream Berry","Dream Berry"],
 ["Sappy Pappy Dream Berry 1g Cured Resin","Dream Berry"],
 ["Sappy Pappy Glacier Valley Sour 1g Cured Resin","Glacier Valley Sour"],
 ["Sappy Pappy Sour Luxx 1g Cured Resin","Sour Luxxe"]
]){
 assert.equal(cleanStrain({strain:raw,product_name:raw,category:"Concentrates"}),expected,
   "Sappy Pappy is product line, not cultivar: "+raw);
}

assert.equal(canonicalBrand("Verist Fields"),"Verist Fields");
for (const raw of ["Mr. Birch Big Stick Torch Top", "Mr Birch Big Stick Torch Top"]) {
 const legacy = {id:"verified-birch-torch-top",retailer:"5D Dispensary LLC",brand:"Mr. Birch",
   strain:raw,master_strain:raw,product_name:raw,raw_scanned_product_name:raw,
   category:"Preroll",package_g:1,price:16,reviewed_identity:true};
 const cards = groupOffers([legacy]);
 assert.equal(cards.length,1, "Missing Torch Top card");
 assert.equal(cards[0].strain,"Torch Top", "Brand/format prefix escaped on Torch Top");
 assert.equal(cards[0].offers[0].displayBrand,"Verist Fields");
}
assert.equal(groupOffers([{strain:"Mochi Melon",brand:"Emerald Fire Farms",category:"Flower",package_g:3.5,retailer:"A",price:45},{strain:"Mochi Melon",brand:"Emerald Farms",category:"Flower",package_g:3.5,retailer:"B",price:47}]).length,1);
assert.equal(groupOffers([{strain:"24K Gold",brand:"Oma",category:"Vape",package_g:1,retailer:"A",price:70},{strain:"24K Gold",brand:"Laketown",category:"Vape",package_g:1,retailer:"B",price:72}]).length,1);
assert.equal(groupOffers([{strain:"Mochi Melon",brand:"Emerald Farms",category:"Flower",package_g:3.5,retailer:"A",price:45},{strain:"Mochi Melon",brand:"Emerald Farms",category:"Preroll",package_g:1,retailer:"B",price:15}]).length,1,"Show the same strain in one card while retaining distinct product forms on each offer");
assert.equal(canonicalBrand("Unwind Cultivation"),"Unwind");
assert.equal(canonicalBrand("Unwind"),"Unwind");
assert.equal(cleanStrain({strain:"Unwind Cultivation Push OG - 0.5g 2ct Preroll"}),"Push OG");
assert.equal(cleanStrain({strain:"Unwind Cultivation Sour Diesel - 1g Tasters (Mixed Flower)"}),"Sour Diesel");
assert.equal(cleanStrain({strain:"Sunset Sherbert",brand:"Campfire Cannabis"}),"Sunset Sherbet");
assert.equal(cleanStrain({strain:"Tropical Cherry",product_family:"Tropical Cherry",product_family_decision:"owner_confirmed_exact_listing",product_name:"3.5g Jar Trop Cherry"}),"Tropicana Cherry");
assert.equal(groupOffers([{strain:"Cake Mix",brand:"Redwood County Weed Management",category:"Preroll",package_g:1,retailer:"5D",price:14},{strain:"Cake Mix",brand:"Redwood",category:"Preroll",package_g:1,retailer:"ABC",price:15}]).length,1);
const sunsetOffers=groupOffers([
 {brand:"Campfire Cannabis",strain:"Sunset Sherbert",category:"Flower",package_g:3.5,retailer:"Levitated",price:49.99},
 {brand:"Campfire Cannabis",strain:"Sunset Sherbet",category:"Flower",package_g:3.5,retailer:"Legacy",price:50}
]);
assert.equal(sunsetOffers.length,1);
assert.equal(sunsetOffers[0].offers.length,2);
assert.equal(packOf({category:"Flower",package_g:3.5}).equivalent,"eighth");
assert.equal(packOf({category:"Flower",package_g:4}).equivalent,"eighth");
assert.equal(packOf({category:"Flower",package_g:3.5}).label,"3.5 g");
assert.equal(packOf({category:"Flower",package_g:4}).label,"3.5 g");
assert.equal(cleanStrain({strain:"Animal Face | Prepacked",category:"Flower"}),"Animal Face");
assert.equal(cleanStrain({strain:"Animal Face Prepacked",category:"Flower"}),"Animal Face");
assert.equal(packOf({category:"Vape",package_g:.5}).equivalent,"0.5");
assert.equal(packOf({category:"Preroll",product_name:"Brand Kush 3x 0.5g preroll",package_g:1.5}).total,1.5);
assert.equal(packOf({category:"Preroll",product_name:"Brand Kush 3x 0.5g preroll",package_g:1.5}).count,3);
assert.equal(packOf({category:"Preroll",product_name:"Brand Kush 3 pack",package_g:1.75}).count,3);
assert.equal(cleanStrain({strain:"Hyperion F1 - Mini PreRolls .5g 2pk",brand:"Dizgo"}),"Hyperion F1");
const noisyZesty=[
 "Avion PreRoll-X | Avion | Zesty Parm | 1 g (CANNABIS FLOWER (PACKAGED))",
 "Zesty Parm | 2-Pack | 1.5gm",
 "Minny Grown Zesty Parm 3.5g",
 "Minny Grown | Zesty Parm | 2pk .75g Preroll | Sativa",
 "OFFER CONDITIONS APPLY Dizgo | Pre-Packaged | Zesty Parm | 3.5g"
];
for(const name of noisyZesty){
 assert.equal(cleanStrain({strain:name,product_name:name,brand:""}),"Zesty Parm");
}
assert.equal(cleanStrain({strain:"1g | Mixed Strains | Indica | Pre-Roll",category:"Preroll"}),"Mixed Strains");
assert.equal(cleanStrain({strain:"Brand | Flower | AK-47 | 3.5g",category:"Flower"}),"AK-47");
assert.equal(cleanStrain({strain:"AK47 | 1g",category:"Flower"}),"AK-47");
const unboundVape = (strain, id) => ({id, brand:"Unbound", category:"Vape", package_g:1, retailer:"Twin Cities Cannabis — Richfield", price:56.66, strain:"Distillate 510 Vape-IX | Unbound | Mixed | 1g | "+strain+" | 1 ct"});
assert.equal(cleanStrain(unboundVape("Grand Daddy Purple","a")),"Granddaddy Purple");
assert.equal(cleanStrain(unboundVape("Super Lemon Haze","b")),"Super Lemon Haze");
assert.equal(cleanStrain(unboundVape("Skywalker OG","c")),"Skywalker OG");
assert.equal(cleanStrain({brand:"Float Cannabis",strain:"Float Distillate 510 Vape-IX | Unbound | Mixed | 1g | Strawberry Haze | 1 ct"}),"Strawberry Haze");
assert.equal(cleanStrain({strain:"Rosin | Mixed | 0.5g Cart",category:"Vape"}),"Mixed Strains");
const distinctVapes=groupOffers([unboundVape("Grand Daddy Purple","a"),unboundVape("Super Lemon Haze","b")]);
assert.equal(distinctVapes.length,2,"Different source strains must not share one card");
assert.equal(groupOffers([{strain:"510 Vape-IX",brand:"Unbound",category:"Vape",package_g:1,retailer:"A",price:50}]).length,0,"Do not display format-only products as strain cards");

const cleanedScreenshot=[
 ["Apple Fritter RCWM 3.5","Redwood County Weed Management","Apple Fritter"],
 ["Tasty Gems Aquamarine Dream .5g Distillate All-In-One Vape","Tasty Gems","Aquamarine Dream"],
 ["Aquamarine Dream | Distillate Disposable | 0.5g | Tasty Gems |","Tasty Gems","Aquamarine Dream"],
 ["Atomic Pop Hybrid 1g Dispo","Lake Leaf","Atomic Pop"],
 ["Avio Autopilot Distillate Infused Preroll 1g 1ct","Avio","Autopilot"],
 ["Bananaconda | Prepacked | 3.5g | Rythm |","RYTHM","Bananaconda"],
 ["Dope Cannabis Live Resin Disposable-IX | d'Ope Cannabis | Banjerine | 1g | Sativa Dominant | 1 ct","","Banjerine"],
 ["Apple Fritter Flower","","Apple Fritter"],
 ["Avion PreRoll-X | Avion | Frodo Squeeze | 1 g (CANNABIS FLOWER (PACKAGED))","","Frodo Squeeze"],
 ["Flower Bag-IX | Grasslandz | Gelato 45 | 3.5g | 1ct (Flowers/Buds - Packaged)","","Gelato 45"],
 ["Flower Bag-IX | Grasslandz | Glue 31 | 3.5g | 1 ct (Flowers/Buds - Packaged)","","Glue 31"]
];
for(const [strain,brand,expected] of cleanedScreenshot){
 assert.equal(cleanStrain({strain,brand}),expected,"Failed to clean "+strain);
}
const aqua=groupOffers([
 {strain:"Tasty Gems Aquamarine Dream .5g Distillate All-In-One Vape",brand:"Tasty Gems",category:"Vape",package_g:.5,retailer:"Levitated",price:49.99},
 {strain:"Aquamarine Dream | Distillate Disposable | 0.5g | Tasty Gems |",brand:"Tasty Gems",category:"Vape",package_g:.5,retailer:"Black Bear",price:65}
]);
assert.equal(aqua.length,1,"Aquamarine Dream should be one card across retailers");
assert.equal(aqua[0].offers.length,2,"Keep both retailer prices");
const fixture=[
{strain:"Lit OG",brand:"Float Cannabis Co.",category:"Flower",package_g:3.5,retailer:"A",price:40},
{strain:"Lit OG",brand:"Float Cannabis Company",category:"Flower",package_g:4,retailer:"B",price:45},
{strain:"Lit OG",brand:"Dizgo",category:"Flower",package_g:3.5,retailer:"C",price:44},
{strain:"Lit OG",brand:"Float Cannabis",category:"Vape",package_g:.5,retailer:"D",price:40}
];
const groups=groupOffers(fixture);
assert.equal(groups.length,1,"Same canonical strain belongs in one comparison card");
assert.equal(groups[0].brand,"Multiple brands");
assert.equal(groups[0].type,"Mixed forms");
assert.equal(groups[0].offers.length,4,"Preserve all retailer/brand/format offers");
assert.equal(groups[0].offers.filter(x=>x.displayBrand==="Float Cannabis"&&x.displayType==="Flower").length,2);
for(const [raw,expected] of [
 ["Verist Gush Kush 5x","Gush Kush"],
 ["Verist Swedish OG","Swedish OG"],
 ["Verist Swedish OG little sticks 5x","Swedish OG"],
 ["Valhalla Select Granola Funk","Granola Funk"],
 ["Verist Valley Frost Flower","Valley Frost"],
 ["Valley Frost 3.5","Valley Frost"]
])assert.equal(cleanStrain({strain:raw,category:"Flower"}),expected,"Incorrect canonical strain: "+raw);
const killer=groupOffers([{id:"auto-a06095f26bd721f77a",retailer:"Dabney's Cannabis Co.",strain:"OFFER CONDITIONS APPLY Trailhead Reserve Killer Cupcake Flower 50/50",product_name:"OFFER CONDITIONS APPLY Trailhead Reserve Killer Cupcake Flower 50/50",brand:"",category:"Flower",package_g:3.5,price:40,url:"https://dabneys.dispensary.shop/rec/all-products/nb/kef"}]);
assert.equal(killer.length,1);
assert.equal(killer[0].strain,"Killer Cupcake");
assert.equal(killer[0].offers[0].displayBrand,"Trailhead Cannabis");
assert.equal(enriched({strain:"Aurora Cannabis LLC Sour Diesel",brand:"Aurora Cannabis LLC"}).displayBrand,"Aurora");
assert.equal(enriched({strain:"Valhalla Select Granola Funk",brand:"Valhalla"}).displayBrand,"Valhalla Cannabis");
for (const [alias, name] of [
 ["Dabney's", "Dabney's Cannabis Co."], ["Danbey's", "Dabney's Cannabis Co."],
 ["Aurora Cannabis LLC", "Aurora"], ["Aurora’s", "Aurora"],
 ["Trailhead", "Trailhead Cannabis"], ["Trailhead Cannabis Company", "Trailhead Cannabis"],
 ["Valhalla Confections", "Valhalla Cannabis"], ["Vahalla Confections", "Valhalla Cannabis"]
]) {
 assert.equal(canonicalBrand(alias), name);
 assert.equal(enriched({brand:alias, reviewed_identity:true}).displayBrand, name);
}
const nightHawk=groupOffers([
 {strain:"Night Hawk",brand:"Dizgo Collective",retailer:"BlooMN Cannabis Company",category:"Preroll",package_g:1,price:17},
 {strain:"Nighthawk",brand:"Dizgo Collective",retailer:"Kodjo's Dispensary",category:"Flower",package_g:3.5,price:40}
]);
assert.equal(nightHawk.length,1,"Night Hawk and Nighthawk must not produce separate cards");
assert.equal(nightHawk[0].strain,"Night Hawk");
assert.equal(nightHawk[0].offers.length,2);
const mendo=groupOffers([
 {strain:"Mendo Breath",retailer:"A",brand:"Brand A",category:"Flower",package_g:3.5,price:45},
 {strain:"Mendo Breath Auto",retailer:"B",brand:"Brand B",category:"Preroll",package_g:1,price:16},
 {strain:"Mendo Breathe",retailer:"C",brand:"Brand C",category:"Concentrate",package_g:0.5,price:40}
]);
assert.equal(mendo.length,1,"Owner-approved Mendo Breath Auto alias must consolidate");
assert.equal(mendo[0].strain,"Mendo Breath");
assert.equal(mendo[0].offers.length,3);
for(const [a,b,expected] of [
 ["The Soap","Soap","Soap"],
 ["Reserve Killer Cupcake","Killer Cupcake","Killer Cupcake"],
 ["Z-Cube","Z Cube","Z Cube"],
 ["Chem Dawg","Chemdawg","Chemdawg"],
 ["Runtz S1","Runtz","Runtz"],
 ["Valhalla Select Granola Funk","Granola Funk","Granola Funk"],
 ["Cherry K 3 pck","Cherry Kush","Cherry Kush"],
 ["TriCross 3 pck","TriCross","TriCross"]
]){
 const merged=groupOffers([
  {strain:a,retailer:"Store A",category:"Flower",package_g:3.5,price:40},
  {strain:b,retailer:"Store B",category:"Preroll",package_g:1,price:15}
 ]);
 assert.equal(merged.length,1,a+" and "+b+" must share one public card");
 assert.equal(merged[0].strain,expected);
 assert.equal(merged[0].offers.length,2);
}
const jacks=groupOffers([
 {strain:"Jack's Delight",retailer:"Store A",category:"Flower",package_g:3.5,price:45},
 {strain:"Jacks Delight 2x",retailer:"Store B",category:"Preroll",package_g:1,price:17},
 {strain:"Jack’s Delight",retailer:"Store C",category:"Flower",package_g:3.5,price:46}
]);
assert.equal(jacks.length,1,"Jack's Delight spelling and pack variants must merge");
assert.equal(jacks[0].strain,"Jack's Delight");
assert.equal(jacks[0].offers.length,3);
const mystic=groupOffers([
 {strain:"Mystic Mint",retailer:"A",brand:"Good Green",category:"Flower",package_g:3.5,price:42},
 {strain:"Good Green (2x) Mystic Mint",retailer:"B",brand:"",category:"Preroll",package_g:1,price:20}
]);
assert.equal(mystic.length,1,"Good Green (2x) Mystic Mint must merge with Mystic Mint");
assert.equal(mystic[0].strain,"Mystic Mint");
assert.equal(mystic[0].offers[1].displayBrand,"Good Green");
const goodGreenJacks=groupOffers([
 {strain:"Good Green Jacks Delight",retailer:"Store A",category:"Flower",package_g:3.5,price:40},
 {strain:"Jack's Delight",retailer:"Store B",category:"Preroll",package_g:1,price:15}
]);
assert.equal(goodGreenJacks.length,1);
assert.equal(goodGreenJacks[0].strain,"Jack's Delight");
assert.equal(goodGreenJacks[0].offers[0].displayBrand,"Good Green");
const governmentOranges=groupOffers([
 {strain:"Government Orange",retailer:"Store A",category:"Flower",package_g:3.5,price:40},
 {strain:"Government Oranges",retailer:"Store B",category:"Concentrate",package_g:1,price:50}
]);
assert.equal(governmentOranges.length,1);
assert.equal(governmentOranges[0].strain,"Government Oranges");
assert.equal(governmentOranges[0].offers.length,2);
const orangeVariants=groupOffers([
 {strain:"Government Oranges Alpha",retailer:"Store A",brand:"FLÖR",category:"Flower",package_g:3.5,price:40},
 {strain:"Government Oranges (Sour)",retailer:"Store A",brand:"FLÖR",category:"Flower",package_g:3.5,price:40},
 {strain:"Government Oranges",retailer:"Store A",brand:"FLÖR",category:"Flower",package_g:3.5,price:40}
]);
assert.deepEqual(orangeVariants.map(card=>card.strain),["Government Oranges"]);
assert.deepEqual(orangeVariants[0].offers.map(offer=>offer.product_variant),["Alpha","Sour",undefined]);
for(const [first,second,canonical] of [
 ["Verist Gush Kush","Verist Gush Kush 5x","Gush Kush"],
 ["Verist Swedish OG","Verist Swedish OG little sticks 5x","Swedish OG"],
 ["Gush Kush","Verist Gush Kush","Gush Kush"],
 ["Swedish OG","Verist Swedish OG","Swedish OG"]
]){
 const cards=groupOffers([
  {strain:first,retailer:"Dabney's Cannabis Co.",brand:"Verist Fields",category:"Preroll",package_g:1,price:14},
  {strain:second,retailer:"Dabney's Cannabis Co.",brand:"Little Sticks",category:"Preroll",package_g:1.75,price:20}
 ]);
 assert.equal(cards.length,1,first+" and "+second+" must be one card");
 assert.equal(cards[0].strain,canonical);
 assert.equal(cards[0].offers.length,2);
}
const dirty=groupOffers([
 {strain:"Stashbox x Loon Labs Live Resin Dirty Laundry",retailer:"Dabney's Cannabis Co.",category:"Concentrate",package_g:1,price:65,brand:""},
 {strain:"Dirty Laundry",retailer:"Other Retailer",category:"Concentrate",package_g:1,price:60,brand:"Stashbox x Loon Labs"}
]);
assert.equal(dirty.length,1,"Stashbox Live Resin Dirty Laundry must merge under cultivar");
assert.equal(dirty[0].strain,"Dirty Laundry");
assert.equal(dirty[0].offers[0].displayBrand,"Stashbox x Loon Labs");
const reviewedOffers=groupOffers([
 {id:"reviewed-flower",strain:"Bourbon Berry",product_family:"Bourbon Berry x Whiskey Zulu",
  reviewed_identity:true,category:"Flower",retailer:"Lucky Strains",package_g:3.5,price:35},
 {id:"reviewed-pack",strain:"Valley Frost",product_family:"Little Sticks",
  brand:"Verist Fields",reviewed_identity:true,category:"Preroll",retailer:"Aurora Cannabis",
  package_g:1.75,pack_count:5,price:32},
 {id:"hemp",strain:"Elm Woods Elm Woods",category:"Flower",retailer:"The Grey Area",
  package_g:3.5,price:25}
]);
assert.deepEqual(reviewedOffers.map(card=>card.strain),["Bourbon Berry","Valley Frost"]);
assert.equal(reviewedOffers[1].offers[0].pack.packLabel,"5 pack × 0.35g");
const frootOffers=groupOffers([
 {strain:"Froot by the Foot",brand:"Looner",category:"Flower",retailer:"Levitated",package_g:3.5,price:45},
 {strain:"PreRoll-IX | Avion | Fruit By The Foot | 1g",brand:"Avion",category:"Preroll",retailer:"Lucky Strains",package_g:1,price:20}
]);
assert.deepEqual(frootOffers.map(card=>card.strain),["Froot by the Foot"]);
assert.deepEqual(new Set(frootOffers[0].offers.map(offer=>offer.displayBrand)),new Set(["Looner","Avio"]));

// Green Apple / FLÖR: a quoted .5gm package label is not a strain.
const subZero={strain:'.5gm"',product_name:'Sub Zero Live Rosin | .5gm"',
 raw_scanned_product_name:'Sub Zero Live Rosin | .5gm"',brand:'Flör',
 retailer:'Green Apple',category:'Concentrates',package_g:0.5,price:65};
assert.equal(cleanStrain(subZero),'Sub Zero');
assert.equal(enriched(subZero).displayStrain,'Sub Zero');
assert.equal(groupOffers([subZero])[0].strain,'Sub Zero');
assert.equal(groupOffers([{...subZero,product_name:'.5gm"',raw_scanned_product_name:'.5gm"'}]).length,0,
 'A package-size-only heading must not become a strain card');

const confirmedAliases=[
 ["Big Dog 3/4 Gram L'ORANGE Sativa","L'Orange","Dogwalkers"],
 ["Gummi-Bear Live Rosin","Gummibears","FLÖR"],
 ["Highnorth Turtle Taffy Discovery Pack","Turtle Taffy",""],
 ["Highnorth White Widow Discovery Pack","White Widow",""],
 ["Highnorth Turtle Taffy","Turtle Taffy",""],
 ["Highnorth White Widow","White Widow",""],
 ["Hyperion","Hyperion F1","Dizgo Collective"],
 ["Hyperion F1","Hyperion F1","Dizgo Collective"],
 ["Little Stick by Verist Fields Double Sour Grape","Double Sour Grape","Verist Fields"],
 ["Little Stick by Verist Fields Platinum Jesus","Platinum Jesus","Verist Fields"],
 ["Mr Birch Big Stick Torch Top","Torch Top","Verist Fields"],
 ["Mr.Birch Little Stick - Swedish OG","Swedish OG","Verist Fields"],
 ["Nighthawk","Night Hawk","Dizgo Collective"],
 ["Night Hawk","Night Hawk","Dizgo Collective"],
 ["Pilot Light 2.0","Pilot Light","FLÖR"],
 ["Pilot Light","Pilot Light","FLÖR"],
 ["Popcorn- Space Boogie","Space Boogie",""],
 ["Purple Cereal Milk","Purple Milk",""],
 ["Mendo Breath Auto","Mendo Breath",""]
];
for(const [title,strain,brand] of confirmedAliases){
 const item={strain:title,product_name:title,brand:brand||"",category:"Flower",package_g:3.5,price:35,retailer:"QA Store"};
 const cards=groupOffers([item]);
 assert.equal(cards.length,1,title+" must have a public card");
 assert.equal(cards[0].strain,strain,title+" must use canonical heading");
 if(brand)assert.equal(cards[0].offers[0].displayBrand,canonicalBrand(brand),title+" must carry correct brand");
}
for(const [left,right] of [
 ["Hyperion","Hyperion F1"],
 ["Night Hawk","Nighthawk"],
 ["Pilot Light","Pilot Light 2.0"],
 ["Mendo Breath","Mendo Breath Auto"],
 ["Purple Milk","Purple Cereal Milk"]
]){
 const cards=groupOffers([left,right].map((name,index)=>({
  strain:name,product_name:name,retailer:"Store "+index,category:"Flower",package_g:3.5,price:40+index
 })));
 assert.equal(cards.length,1,left+" / "+right+" must consolidate while retaining both offers");
 assert.equal(cards[0].offers.length,2,left+" / "+right+" offers preserved");
}


const legacySunset=groupOffers([
 {strain:"Sunset Sherbert",master_strain:"Sunset Sherbert",brand:"Rewind",category:"Flower",package_g:3.5,retailer:"Store A",price:39},
 {strain:"Sunset Sherbet",master_strain:"Sunset Sherbet",brand:"Campfire Cannabis",category:"Flower",package_g:7,retailer:"Store B",price:75}
]);
assert.equal(legacySunset.length,1,"Legacy master headings must not split Sunset Sherbet");
assert.equal(legacySunset[0].strain,"Sunset Sherbet");
assert.equal(legacySunset[0].offers.length,2);
assert(legacySunset[0].offers.some(o=>o.displayBrand==="Rewind"),"Rewind remains a brand");
assert.equal(groupOffers([{strain:"Rewind",brand:"Rewind",category:"Flower",package_g:3.5,retailer:"Store A",price:40}]).length,0,"Brand-only Rewind is not a cultivar");


const newlyFlagged=[
 ["d'Ope Cannabis Anthos Blend |","Anthos Blend","D'Ope","Concentrates"],
 ["Highnorth Turtle Taffy Discovery Pack","Turtle Taffy",null,"Flower"],
 ["Highnorth White Widow Discovery Pack","White Widow",null,"Flower"],
 ["Minny Grown Minny Grown | Flower | FrankenPine","Franken Pine","Minny Grown","Flower"],
 ["Minny Grown Sour Lemons","Sour Lemons","Minny Grown","Flower"],
 ["Mischief Premium Atlas Froot by the Foot","Froot by the Foot","Mischief Cannabis","Flower"],
 ["Mr. Birch Big Stick Torch Top","Torch Top","Verist Fields","Preroll"],
 ["NorthPark 510 Vape Cart-IX | Gelato #41","Gelato 41","Northpark","Concentrates"],
 ["NorthPark OG Kush Cart","OG Kush","Northpark","Concentrates"],
 ["R & D R & D Pharms | Black Maple | Pre-pack","Black Maple 22","R & D Farms","Flower"],
 ["Rewind Aloha Sugar","Aloha Sugar","Rewind","Concentrates"],
 ["Rewind Daily Grape","Daily Grape","Rewind","Concentrates"],
 ["Rewind Kanobi Sunset","Kanobi Sunset","Rewind","Concentrates"],
 ["Rewind Killer Cupcake","Killer Cupcake","Rewind","Concentrates"],
 ["Turtle Taffy - 2-Pack","Turtle Taffy",null,"Preroll"],
 ["Turtle Taffy - 8-Pack","Turtle Taffy",null,"Preroll"],
 ["Verist Fields Verist Fields | Cured Resin | Sappy Pappy | Dream Berry","Dream Berry","Verist Fields","Concentrates"],
 ["Verist Fields Verist Fields | Pre-Packaged | Double Sour Grapes","Double Sour Grape","Verist Fields","Flower"],
 ["Float Float | Pre-Packaged | Gorilla Zkittles","Gorilla Zkittlez","Float Cannabis","Flower"],
 ["Float Magic Marker","Magic Marker","Float Cannabis","Flower"],
 ["Shine Grand Daddy Purple","Granddaddy Purple","&Shine","Flower"],
 ["Trailhead Trailhead | Pre-Packaged | Gastronaunt","Gastronaut","Trailhead Cannabis","Flower"]
];
for(const [title,expectedStrain,expectedBrand,category] of newlyFlagged){
 const offer={id:"qa-"+title,retailer:"Example Store",strain:title,product_name:title,master_strain:title,
   brand:"",category,package_g:category==="Concentrates"?0.5:3.5,price:40};
 const cards=groupOffers([offer]);
 assert.equal(cards.length,1,"Missing card after correction: "+title);
 assert.equal(cards[0].strain,expectedStrain,"Wrong cultivar: "+title);
 if(expectedBrand)assert.equal(cards[0].offers[0].displayBrand,expectedBrand,"Wrong brand: "+title);
}
for(const [variant,plain] of [
 ["Turtle Taffy - 2-Pack","Turtle Taffy"],
 ["Turtle Taffy - 8-Pack","Turtle Taffy"],
 ["Rewind Killer Cupcake","Killer Cupcake"],
 ["Float Magic Marker","Magic Marker"]
]){
 const originals=[variant,plain].map((name,i)=>({retailer:"Retailer "+i,strain:name,product_name:name,
   brand:i?"":(variant.startsWith("Rewind")?"Rewind":variant.startsWith("Float")?"Float Cannabis":""),
   category:"Flower",package_g:3.5,price:40+i}));
 const cards=groupOffers(originals);
 assert.equal(cards.length,1,"Duplicate shopper cards for "+variant);
 assert.equal(cards[0].offers.length,2,"Distinct offers lost for "+variant);
}
const auroraStrawneapple=groupOffers([{strain:"Aurora Cannabis LLC Strawneapple",product_name:"Aurora Cannabis LLC Strawneapple | 3.5G",master_strain:"Aurora Cannabis LLC Strawneapple",brand:"Aurora Cannabis LLC",retailer:"Aurora Cannabis MN Dispensary",category:"Flower",package_g:3.5,price:36}]);
assert.equal(auroraStrawneapple.length,1);
assert.equal(auroraStrawneapple[0].strain,"Strawneapple");
assert.equal(auroraStrawneapple[0].offers[0].displayBrand,"Aurora");
assert.equal(auroraStrawneapple[0].offers[0].pack.total,3.5);
console.log("MNtrees normalization tests passed");

// Final public grouping must defeat stale review/master headings containing
// retailer and format, while preserving strain identity and offer metadata.
for(const [legacy,correct] of [
 ["Highnorth Turtle Taffy Discovery Pack","Turtle Taffy"],
 ["Highnorth White Widow Discovery Pack","White Widow"],
 ["Highnorth Turtle Taffy","Turtle Taffy"],
 ["Highnorth White Widow","White Widow"]
]){
 const old={id:"highnorth-regression-"+correct,retailer:"Highnorth",
   strain:legacy,master_strain:legacy,product_name:legacy,
   brand:"Brand not confirmed",category:"Flower",package_g:2,price:35,
   reviewed_identity:true};
 const cards=groupOffers([old]);
 assert.equal(cards.length,1,"Retailer prefix must not create or drop "+correct);
 assert.equal(cards[0].strain,correct,"Incorrect Highnorth strain heading: "+legacy);
}
assert.equal(groupOffers([{id:"bad-highnorth",retailer:"Highnorth",
  strain:"Highnorth Unverified Discovery Pack",product_name:"Highnorth Unverified Discovery Pack",
  category:"Flower",package_g:2,price:35}]).length,0,
  "Unknown retailer-prefixed identity must not become a strain card");

// Rewind is a brand; legacy prefixed titles must merge into the actual
// cultivar card, and ambiguous Rewind SKUs must stay out of strain headings.
for(const [raw,canonical] of [
 ["Rewind Aloha Sugar","Aloha Sugar"],
 ["Rewind Daily Grape","Daily Grape"],
 ["Rewind Kanobi Sunset","Kanobi Sunset"],
 ["Rewind Killer Cupcake","Killer Cupcake"]]){
 const legacy={id:"rewind-"+canonical,retailer:"Unwind",brand:"Rewind",
   strain:raw,master_strain:raw,product_name:raw,category:"Concentrates",
   package_g:0.5,price:39,reviewed_identity:true};
 const grouped=groupOffers([legacy]);
 assert.equal(grouped.length,1,raw+" should produce exactly one cultivar");
 assert.equal(grouped[0].strain,canonical,raw+" should not retain Rewind");
 assert.equal(grouped[0].offers[0].displayBrand,"Rewind");
}
assert.equal(groupOffers([{id:"rewind-unverified",retailer:"Unwind",
 strain:"Rewind Mystery Product",product_name:"Rewind Mystery Product",
 brand:"Rewind",category:"Concentrates",package_g:0.5,price:30}]).length,0,
 "Unverified Rewind product must not become a strain card");
