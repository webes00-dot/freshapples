'use strict';
const assert=require('node:assert/strict');
const catalog=require('../catalog-model.js');
const make=(brand,grams,category='Flower',strain='Animal Scout',retailer='Test retailer')=>({
 retailer,brand,strain,product_family:strain,product_name:strain+' '+grams+'g',
 category,package_g:grams,price:40+grams,url:'https://example.com/menu/'+brand+'/'+grams+'/'+category
});
const grouped=catalog.groupOffers([
 make('RYTHM',3.5),make('RHYTHM',7),make('Rythm',4),
 make('RYTHM',1,'Preroll'),make('Other Brand',3.5)
]);
assert.equal(grouped.length,1,'shared strain has one card across brands, weights, and forms');
assert.equal(grouped[0].offers.length,5);
assert.equal(grouped[0].brand,'Multiple brands');
assert.equal(grouped[0].type,'Mixed forms');
assert.equal(catalog.canonicalBrand('RHYTHM'),'RYTHM');
// Animal Face is one strain card even when Big Dog and Dogwalkers are
// separate consumer brands. Retain individual retailer offers and weights.
const animalFace = catalog.groupOffers([
 make('Big Dog',0.75,'Preroll','Animal Face','American Made Cannabis'),
 make('Dogwalkers',0.75,'Preroll','Animal Face','Black Bear Dispensary'),
 make('Dogwalkers',1.75,'Preroll','Animal Face','BlooMN Cannabis Company')
]);
assert.equal(animalFace.length,1,'Animal Face must not be split by brand');
assert.equal(animalFace[0].offers.length,3);
assert.equal(animalFace[0].brand,'Multiple brands');
assert.deepEqual([...new Set(animalFace[0].offers.map(x=>x.displayBrand))].sort(),['Big Dog','Dogwalkers']);
assert.deepEqual([...new Set(animalFace[0].offers.map(x=>x.pack.total))].sort(),[0.75,1.75]);
// Every strain is a single card no matter which brand/form is offered.
// Filtering to a brand yields one subset of the same strain, not a new
// brand-keyed identity.
const mixedOffers=[
 make('Big Dog',0.75,'Preroll','Animal Face','American Made Cannabis'),
 make('Dogwalkers',1.75,'Preroll','Animal Face','BlooMN Cannabis Company'),
 make('RYTHM',3.5,'Flower','Animal Face','Green Goods')
];
const mixedAnimal=catalog.groupOffers(mixedOffers);
assert.equal(mixedAnimal.length,1);
assert.equal(mixedAnimal[0].brand,'Multiple brands');
assert.equal(mixedAnimal[0].type,'Mixed forms');
assert.equal(mixedAnimal[0].offers.length,3);
const byBrand=catalog.groupOffers(mixedOffers.filter(x=>x.brand==='Dogwalkers'));
assert.equal(byBrand.length,1);
assert.equal(byBrand[0].strain,'Animal Face');
assert.equal(byBrand[0].offers.length,1);
assert.equal(byBrand[0].offers[0].displayBrand,'Dogwalkers');
const separated=catalog.groupOffers([...mixedOffers,make('RYTHM',3.5,'Flower','Animal Scout','Green Goods')]);
assert.equal(separated.length,2,'Distinct strain identities must remain separate');
// Cross-feed duplicate captures use different URLs but refer to one SKU.
const crossFeed=(id,overrides={})=>({
 id,retailer:'ABC Cannabis Co.',retailer_id:'MICRO-L25-001251-01-AUR',
 brand:'Redwood County Weed Management',strain:'Cake Mix',category:'Flower',
 package_g:3.5,price:50,product_name:'Cake Mix Flower',
 url:'https://example.org/'+id,...overrides
});
const cake=catalog.groupOffers([
 crossFeed('source-pdp',{url:'https://example.org/rec/flower/pdp/cake-mix/v/123'}),
 crossFeed('source-menu',{url:'https://example.org/rec/menu'})
]);
assert.equal(cake.length,1);
assert.equal(cake[0].offers.length,1,'Same store SKU across different URLs must display once');
assert.equal(cake[0].offers[0].id,'source-pdp','Keep direct product link over generic menu');
const candy=catalog.groupOffers([
 {...crossFeed('joint-commerce',{retailer_id:'MICRO-L25-000999-01-AUR',retailer:'Green Canopy',strain:'Candy Cigarette',brand:'Emerald Farms',price:55})},
 {...crossFeed('official',{retailer_id:'MICRO-L25-000999-01-AUR',retailer:'Green Canopy',strain:'Candy Cigarette',brand:'Emerald Farms',price:55,url:'https://example.org/rec/flower/pdp/candy-cigarette/v/123'})}
]);
assert.equal(candy[0].offers.length,1,'Candy Cigarette duplicate third-party capture');
const cheetah=catalog.groupOffers([
 ...['Cheetah Piss','OFFER CONDITIONS APPLY Native Cuts Cheetah Piss',
     'OFFER BUY 2 Native Cuts Cheetah Piss'].map((title,i)=>crossFeed('cheetah-'+i,{
       retailer:'Green Leaf Depot',retailer_id:'MICRO-L25-000398-01-AUR',
       strain:'Cheetah Piss',brand:'Native Cuts',price:45,product_name:title
     }))
]);
assert.equal(cheetah[0].offers.length,1,'Promo ribbons must not create multiple offers');
const cap=catalog.groupOffers([
 crossFeed('cap-research',{retailer:'BlooMN Cannabis Company',retailer_id:'MICRO-L25-000565-01-AUR',
    strain:'Cap Junky',brand:'Float Cannabis',category:'Preroll',package_g:1,price:13}),
 crossFeed('cap-auto',{retailer:'BlooMN Cannabis Company',retailer_id:'MICRO-L25-000565-01-AUR',
    strain:'Cap Junky',brand:'Float Cannabis',category:'Preroll',package_g:1,price:13})
]);
assert.equal(cap[0].offers.length,1,'Same retailer Cap Junky preroll must not repeat');
for(const [change,expected] of [
 [{package_g:7},2],[{price:51},2],[{brand:'Other Brand'},2],
 [{category:'Preroll'},2],[{retailer_id:'ANOTHER-LOCATION'},2],
 [{product_name:'Cake Mix Premium Flower'},2]
]){
 const grouped=catalog.groupOffers([crossFeed('orig'),crossFeed('changed',change)]);
 assert.equal(grouped[0].offers.length,expected,'Distinct SKU variant must survive: '+JSON.stringify(change));
}
const aliases=[
 ['Float Cannabis','Gorilla Zkittles','Gorilla Zkittlez'],
 ['Float Cannabis','Gorilla Zkittlez','Gorilla Zkittlez'],
 ['Unbound','Grand Daddy Purple','Granddaddy Purple'],
 ['Unbound','Granddaddy Purple','Granddaddy Purple'],
 ['Mischief Cannabis','Gummibears (Premium) -3.5g','Gummibears'],
 ['Avio','Gummy Gas-Infused Preroll','Gummy Gas'],
 ['Redwood County Weed Management','Halle Berry-RCWM-3.5','Halle Berry'],
 ['High Definition','High Definition Mendo Breath','Mendo Breath'],
 ['Dizgo Collective','Hyperion','Hyperion F1'],
 ['Dizgo Collective','Hyperion F1','Hyperion F1'],
 ['Redwood County Weed Management','Jelly Breath-RCWM-3.5','Jelly Breath'],
 ['D\'Ope','Lemon Medusa Live Resin','Lemon Medusa'],
 ['Marawanna','Live Rosin Octane Mintz','Octane Mintz'],
 ['Unbound','Mac V2 5pck #1','MAC V2'],
 ['Marawanna','marawanna Live Rosin Dulce De Fresa','Dulce de Fresa'],
 ['Marawanna','marawanna Live Rosin Tropic Fresa','Tropic Fresa'],
 ['Avion','Mendo Breath Auto','Mendo Breath'],
 ['Minny Grown','Night Hawk | 2-Pack | 1.5gm','Night Hawk'],
 ['Dizgo','Nighthawk 3.5g','Night Hawk'],
 ['Emerald Farms','Planet of the Grapes','Planet of the Grapes'],
 ['Emerald Farms','Emerald Fire Farms Planet of the Grapes - 1/8oz','Planet of the Grapes']
];
for(const [brand,strain,expected] of aliases){
 assert.equal(catalog.cleanStrain({brand,strain,product_name:strain}),expected,
  'expected canonical strain for '+brand+' / '+strain);
}
assert.equal(catalog.groupOffers([
 make('Float Cannabis',1,'Preroll','Gorilla Zkittles','Fort Road'),
 make('Float Cannabis',1,'Preroll','Gorilla Zkittlez','Green Apple')
]).length,1);
const duplicate=make('Trailhead Cannabis',3.5,'Flower','Gastronaut','Do Be Kind');
assert.equal(catalog.groupOffers([duplicate,{...duplicate,id:'second capture'}])[0].offers.length,1);
assert.equal(catalog.typeOf({id:'b922017567392166d488',category:'Flower'}),'Preroll');
assert.equal(catalog.canonicalBrand('Avion'),'Avio');
assert.equal(catalog.enriched({brand:'',brand_family:'',product_name:'marawanna Live Rosin Tropic Fresa',strain:'Tropic Fresa',category:'Concentrate'}).displayBrand,'Marawanna');
assert.equal(catalog.groupOffers([
 make('Avio',1,'Preroll','Mendo Breath Auto','Fort Road'),
 make('Avion',1,'Preroll','Mendo Breath Auto','Fort Road 2')
]).length,1);
assert.equal(catalog.cleanStrain({brand:'Dogwalkers',strain:'animal face .35 x 5 dogwalker',category:'Pre-Rolls',package_g:1.75}),'Animal Face');
assert.equal(catalog.typeOf({brand:'Dogwalkers',category:'Pre-Rolls'}),'Preroll');
assert.equal(catalog.packOf({product_name:'animal face .35 x 5 dogwalker',category:'Pre-Rolls',package_g:1.75}).total,1.75);
assert.equal(catalog.packOf({product_name:'animal face .35 x 5 dogwalker',category:'Pre-Rolls',package_g:1.75}).count,5);
for(const [name,expected] of [
 ['Valhalla Confections','Valhalla Cannabis'],['Vahalla Confections','Valhalla Cannabis'],['Valhalla Cannabis','Valhalla Cannabis'],
 ['R & D Farms','R & D Farms'],['R & D Pharms','R & D Farms'],
 ['Flor Fina','FLÖR'],['Flor','FLÖR'],
 ['Native Care','Native Care'],['NativeCare','Native Care']]){
 assert.equal(catalog.canonicalBrand(name),expected,'brand alias '+name);
}
assert.equal(catalog.packOf({category:'Flower',package_g:7}).equivalent,'quarter');
assert.equal(catalog.packOf({category:'Flower',package_g:4}).equivalent,'eighth');
for(const weight of [0.9,1,1.0,1.05]){
 assert.equal(catalog.filterSize({category:'Preroll',package_g:weight}), '1 g');
}
for(const weight of [3.5,4]){
 assert.equal(catalog.filterSize({category:'Flower',package_g:weight}), '3.5 g');
}
assert.equal(catalog.filterSize({category:'Flower',package_g:7}), '7 g');
assert.equal(catalog.filterSize({category:'Preroll',package_g:1.75}), '1.75 g');
assert.equal(catalog.packOf({category:'Preroll',package_g:0.9}).total,0.9);
assert.equal(catalog.packOf({category:'Preroll',package_g:1.05}).total,1.05);
assert.equal(catalog.cleanStrain({strain:'Cherry K 3 pck',product_name:'Cherry K 3 pck',category:'Preroll'}),'Cherry Kush');
assert.equal(catalog.cleanStrain({strain:'Co. Lime Ice',product_name:'Co. Lime Ice'}),'Lime Ice');
assert.equal(catalog.cleanStrain({strain:'Cultivation Campfire Cannabis Soap',product_name:'Cultivation Campfire Cannabis Soap',brand:'Campfire Cannabis'}),'Soap');
assert.equal(catalog.groupOffers([make('Campfire Cannabis',3.5,'Flower','Soap','Store One'),make('Campfire Cannabis',3.5,'Flower','Cultivation Campfire Cannabis Soap','Store Two')]).length,1);
assert.equal(catalog.cleanStrain({strain:'TriCross 3 pck',product_name:'TriCross 3 pck',category:'Preroll'}),'TriCross');
assert.equal(catalog.groupOffers([make('Wright Way Farms',1,'Preroll','TriCross','Store One'),make('Wright Way Farms',1,'Preroll','TriCross 3 pck','Store Two')]).length,1);
assert.equal(catalog.cleanStrain({strain:'The Soap',product_name:'The Soap'}),'Soap');
assert.equal(catalog.groupOffers([make('Campfire Cannabis',3.5,'Flower','Soap','Store One'),make('Campfire Cannabis',3.5,'Flower','The Soap','Store Two')]).length,1);
assert.equal(catalog.cleanStrain({strain:'Select Granola Funk',product_name:'Select Granola Funk'}),'Granola Funk');
assert.equal(catalog.groupOffers([make('Valhalla',3.5,'Flower','Granola Funk','Store One'),make('Valhalla',3.5,'Flower','Select Granola Funk','Store Two')]).length,1);
assert.equal(catalog.cleanStrain({strain:'Runtz S1',product_name:'Runtz S1'}),'Runtz');
assert.equal(catalog.groupOffers([make('RYTHM',3.5,'Flower','Runtz','Store One'),make('RYTHM',7,'Flower','Runtz S1','Store Two')]).length,1);

const skywalkerCases=[
 ['Skywalker','Skywalker'],
 ['Sky Walker','Skywalker'],
 ['Skywalker Flower','Skywalker'],
 ['Skywalker Strain','Skywalker'],
 ['Sky Walker OG','Skywalker OG'],
 ['Skywalker OG Flower','Skywalker OG'],
 ['Skywalker Kush','Skywalker Kush'],
 ['Sky Walker Kush','Skywalker Kush']
];
const skywalkerOffers=skywalkerCases.map(([strain],i)=>({
 id:'skywalker-'+i,retailer:'Skywalker Test Retailer',
 retailer_id:'skywalker-retailer',brand:'Test Brand',strain,product_name:strain,
 product_family:strain,category:'Flower',package_g:3.5,price:40+i,
 url:'https://example.com/skywalker/'+i
}));
const skywalkerGroups=catalog.groupOffers(skywalkerOffers);
assert.equal(skywalkerGroups.length,1,'Show one Skywalker comparison card');
assert.equal(skywalkerGroups[0].strain,'Skywalker');
assert.equal(skywalkerGroups[0].offers.length,8,'Retain all individual offers from all Skywalker variants');
assert.equal(skywalkerGroups[0].offers.filter(x=>String(x.product_variant||'').includes('Skywalker OG')).length,2);
assert.equal(skywalkerGroups[0].offers.filter(x=>String(x.product_variant||'').includes('Skywalker Kush')).length,2);
assert(skywalkerGroups[0].offers.every(x=>x.price>0),'Do not lose offers or prices');

// Granddaddy aliases are one canonical strain; no brand or package data changes.
const purpleAliases=['Grandaddy Purple','Grand Daddy Purp','Granddaddy Purple','Granddaddy Purp','Granddaddy','GDP'];
const granddaddyOffers=purpleAliases.map((strain,i)=>({
 id:'granddaddy-consolidation-'+i,strain,product_name:strain,
 product_family:strain,master_strain:strain,brand:'Unbound',
 retailer:'Catalog QA',retailer_id:'qa-store',category:'Concentrates',
 package_g:1,price:50+i,url:'https://example.com/purple/'+i
}));
const granddaddyGroups=catalog.groupOffers(granddaddyOffers);
assert.equal(granddaddyGroups.length,1,'All Granddaddy spellings must render as one strain card');
assert.equal(granddaddyGroups[0].strain,'Granddaddy Purple');
assert.equal(granddaddyGroups[0].offers.length,purpleAliases.length);
const trailheadSource={
 id:'unidentified-trailhead',strain:'farms Trailhead',
 product_name:'farms Trailhead',product_family:'farms Trailhead',
 retailer:'Catalog QA',retailer_id:'qa-store',category:'Flower',
 package_g:3.5,price:50,url:'https://example.com/trailhead'
};
assert.equal(catalog.groupOffers([trailheadSource]).length,0,'Do not publish a reversed brand-only title as a cultivar');


const displayedIssues=[
 ['Trailhead Killer Cupcake','Killer Cupcake','Trailhead Cannabis'],
 ['Trailhead Octane Mintz','Octane Mintz','Trailhead Cannabis'],
 ['Dizgo Medusa (2 x','Medusa','Dizgo Collective'],
 ['Medusa (2 x','Medusa',null]
];
const pendingCards=displayedIssues.map(([strain],i)=>({
 id:'owner-display-issue-'+i,strain,product_name:strain,product_family:strain,
 master_strain:strain,brand:'',category:i<2?'Flower':'Preroll',
 package_g:i<2?3.5:1,price:i<2?52.05:16.02,
 retailer:'The Grey Area',retailer_id:'grey-area',
 url:'https://example.com/owner-display/'+i
}));
const fixedGroups=catalog.groupOffers(pendingCards);
assert.equal(fixedGroups.length,3,'Medusa packaging variants must combine into one card');
for(const [strain,heading,brand] of displayedIssues){
 const group=fixedGroups.find(g=>g.strain===heading);
 assert(group,'Missing corrected group for '+strain);
 if(brand)assert(group.offers.some(o=>o.displayBrand===brand),'Missing correct brand for '+strain);
}
assert.equal(fixedGroups.find(g=>g.strain==='Medusa').offers.length,2);
assert(fixedGroups.every(g=>!/^trailhead\b|\(2\s*x/i.test(g.strain)),'No vendor or pack prefixes in headings');


const fogDogTitles=['Cannabis Fog Dog (Indica)','Cannabis Fog Dog','Fog Dog','FLÖR Fog Dog- 3.5- Flor 1/8 oz','Indica FLÖR Fog Dog- 3.5- Flor 1/8 oz'];
const fogDogOffers=fogDogTitles.map((strain,i)=>({
 id:'fog-dog-regression-'+i,strain,product_name:strain,product_family:strain,
 master_strain:strain,brand:i===2?'Northpark':'',category:'Flower',
 package_g:3.5,price:42+i,retailer:'Fog Dog Test Retailer',
 retailer_id:'fog-dog-store',url:'https://example.com/fog-dog/'+i
}));
const fogDogGroups=catalog.groupOffers(fogDogOffers);
assert.equal(fogDogGroups.length,1,'Fog Dog and Cannabis Fog Dog (Indica) must group together');
assert.equal(fogDogGroups[0].strain,'Fog Dog');
assert.equal(fogDogGroups[0].offers.length,5);
assert.equal(fogDogGroups[0].offers.filter(o=>o.displayBrand==='FLÖR').length,2,'FLÖR flower titles must preserve brand identity');

console.log('MNtrees catalog grouping and canonical-name checks passed');
