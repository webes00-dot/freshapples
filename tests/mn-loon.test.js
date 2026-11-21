const assert=require('node:assert/strict');
const catalog=require('../catalog-model.js');
const rows=[
 ['Mnl Lemon cherry gelato .5','Lemon Cherry Gelato'],
 ['Mnl Nyc diesel 1/2 gram','NYC Diesel'],
 ['Mnl Orange creamsicle .5','Orange Creamsicle'],
 ['Mnl Pinke rozay','Pink Rozay'],
 ['Mnl Watermelon.5','Watermelon'],
 ['MnLoon NYC Diesel','NYC Diesel']
];
const offers=rows.map(([strain],i)=>({
 id:'mn-loon-test-'+i,
 strain,product_name:strain,brand:'',
 retailer:i===5?'Wild River Dispensary':'ABC Cannabis Co.',
 retailer_id:i===5?'other-store':'abc-store',
 category:'Concentrates',package_g:.5,price:40+i,url:'https://example.com/p/'+i
}));
for(let i=0;i<offers.length;i++){
 const e=catalog.enriched(offers[i]);
 assert.equal(e.displayStrain,rows[i][1],rows[i][0]);
 assert.equal(e.displayBrand,'MN Loon',rows[i][0]);
}
const groups=catalog.groupOffers(offers);
assert.equal(groups.filter(g=>g.strain==='NYC Diesel').length,1);
assert.equal(groups.find(g=>g.strain==='NYC Diesel').offers.length,2);

// Owner-confirmed brand/strain separation and cultivar heading consolidation.
const ownerCases=[
 ['Looner Wild Grape','Wild Grape','Looner'],
 ['Looner Looner Wild Grape','Wild Grape','Looner'],
 ['Elevate Strawberry Lemonade','Strawberry Lemonade','Elevated Botanicals'],
 ['Elevated Botanicals Strawberry Lemonade','Strawberry Lemonade','Elevated Botanicals'],
 ['Grandaddy Purple','Granddaddy Purple','Unbound'],
 ['Grand Daddy Purple','Granddaddy Purple','Unbound'],
 ['Granddaddy Purp','Granddaddy Purple','Unbound']
];
const canonicalOffers=ownerCases.map(([strain,,brand],i)=>({
 id:'owner-strain-test-'+i,strain,product_name:strain,brand:brand==='Unbound'?brand:'',
 retailer:'Test Retailer',retailer_id:'owner-test-store',category:'Flower',
 package_g:3.5,price:40+i,url:'https://example.com/owner/'+i
}));
for(let i=0;i<canonicalOffers.length;i++){
 const actual=catalog.enriched(canonicalOffers[i]);
 assert.equal(actual.displayStrain,ownerCases[i][1],ownerCases[i][0]);
 assert.equal(actual.displayBrand,ownerCases[i][2],ownerCases[i][0]);
}
const canonicalGroups=catalog.groupOffers(canonicalOffers);
assert.equal(canonicalGroups.filter(g=>g.strain==='Granddaddy Purple').length,1);
assert.equal(canonicalGroups.find(g=>g.strain==='Granddaddy Purple').offers.length,3);


// Confirm the approved scan order separates brands and package counts from strains.
const latestCases=[
 ['Cannabis Fog Dog','Fog Dog',null],
 ['Dizgo Medusa','Medusa','Dizgo Collective'],
 ['Emerald Fire Farms Pineapple Burst','Pineapple Burst','Emerald Farms'],
 ['Frodo Squeeze 3 x','Frodo Squeeze',null],
 ['Native Cuts Cheetah','Cheetah Piss','Native Cuts'],
 ['Native Cuts MAC','MAC-1','Native Cuts'],
 ['ON SALE Native Cuts Cheetah Piss Flower','Cheetah Piss','Native Cuts'],
 ['ON SALE Native Cuts MAC-1 Flower 50/50','MAC-1','Native Cuts']
];
for(let i=0;i<latestCases.length;i++){
 const [strain,expected,brand]=latestCases[i];
 const offer={id:'new-issue-'+i,strain,product_name:strain,brand:'',
 category:'Flower',package_g:3.5,price:45,retailer:'Test Retailer',
 retailer_id:'test-location',url:'https://example.com/issue/'+i};
 const actual=catalog.enriched(offer);
 assert.equal(actual.displayStrain,expected,strain);
 if(brand)assert.equal(actual.displayBrand,brand,strain);
}


const stalePublished=[{
 id:'stale-mnl-abc',strain:'Mnl Nyc diesel 1/2 gram',
 product_name:'Mnl Nyc diesel 1/2 gram',product_family:'Mnl Nyc diesel 1/2 gram',
 brand:'Mnl',category:'Concentrates',package_g:0.5,price:40,
 retailer:'ABC Cannabis Co.',retailer_id:'abc-store',
 url:'https://example.com/mnl/abc'
},{
 id:'stale-mnloon-wild',strain:'MnLoon NYC Diesel',
 product_name:'MnLoon NYC Diesel',product_family:'MnLoon NYC Diesel',
 brand:'',category:'Concentrates',package_g:0.5,price:50,
 retailer:'Wild River Dispensary',retailer_id:'wild-river-store',
 url:'https://example.com/mnl/wild'
}];
const staleGroups=catalog.groupOffers(stalePublished);
assert.equal(staleGroups.filter(g=>g.strain==='NYC Diesel').length,1);
assert.equal(staleGroups.find(g=>g.strain==='NYC Diesel').offers.length,2);
assert(staleGroups.every(g=>!/^mnl(?:oon)?\\b/i.test(g.strain)));
assert(staleGroups.find(g=>g.strain==='NYC Diesel').offers.every(o=>o.displayBrand==='MN Loon'));


const remainingCards=[
 ['Mnl Orange creamsicle .5','Orange Creamsicle'],
 ['Mnl Watermelon.5','Watermelon']
];
for(const [raw,canonical] of remainingCards){
 const offer={
  id:'last-two-'+canonical,strain:raw,product_name:raw,product_family:raw,
  master_strain:raw,brand:'Mnl',category:'Concentrates',
  package_g:0.5,price:40,retailer:'ABC Cannabis Co.',
  retailer_id:'abc-store',url:'https://example.com/product/'+canonical
 };
 const groups=catalog.groupOffers([offer]);
 assert.equal(groups.length,1);
 assert.equal(groups[0].strain,canonical,raw);
 assert.equal(groups[0].offers[0].displayBrand,'MN Loon',raw);
 assert.equal(groups[0].offers[0].pack.total,0.5,raw);
 assert.equal(groups[0].offers[0].price,40,raw);
}


const dizgoCases=[
 ['Dizgo Medusa (2 x','Medusa'],
 ['Dizgo TriCross','TriCross'],
 ['Dizgo TriCross 3 pck Flower','TriCross'],
 ['Dizgo Collective TriCross Prerolls - 3 pack Preroll 50/50','TriCross']
];
for(let i=0;i<dizgoCases.length;i++){
 const [raw,canonical]=dizgoCases[i];
 const offer={id:'dizgo-test-'+i,strain:raw,product_name:raw,
  product_family:raw,master_strain:raw,brand:'',category:'Preroll',
  package_g:1,price:16.02,retailer:'The Grey Area',
  retailer_id:'grey-area',url:'https://example.com/dizgo/'+i};
 const grouped=catalog.groupOffers([offer]);
 assert.equal(grouped.length,1,raw);
 assert.equal(grouped[0].strain,canonical,raw);
 assert.equal(grouped[0].offers[0].displayBrand,'Dizgo Collective',raw);
 assert.equal(grouped[0].offers[0].price,16.02,raw);
}

console.log('MN Loon naming and group normalization passed');
