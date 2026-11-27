import assert from 'node:assert/strict';
import test from 'node:test';
import model from '../../catalog-model.js';
import {menuIdentityResolver} from '../../src/menu-title.js';

const directory = [
  {name: 'Campfire Cannabis', aliases: []},
  {name: 'Float Cannabis', aliases: ['Float']},
  {name: 'Verist Fields', aliases: ['Mr. Birch', 'Big Dog', 'Big Dogs']},
  {name: 'Redwood County Weed Management', aliases: ['RCWM']},
  {name: 'Unbound', aliases: []},
  {name: 'FLÖR', aliases: ['HMP LLC']},
  {name: 'Purple Prince', aliases: []},
];
const canonical = ['Runtz', 'Fight Club', 'Mac V2', 'Royal Oasis', 'Apple Fritter', 'Cake Mix',
  'Uptown Tart', 'Mac Stomper', "Mike's Strawberry Lemonade", 'Cap Junky'];
const resolve = menuIdentityResolver(directory, label => {
  const match = canonical.find(name => name.toLowerCase() === String(label ?? '').toLowerCase());
  return match ? {canonical_name: match} : undefined;
}, model.enriched);
const cases = [
  ['Campfire Cannabis Runtz | 3.5g | 19.40%', 'Runtz | 3.5g | 19.40%', 'Campfire Cannabis', 'Flower', 3.5, 'Runtz', 'Campfire Cannabis'],
  ['Campfire Cannabis Fight Club | 3.5g | 20.32%', 'Fight Club | 3.5g | 20.32%', 'Campfire Cannabis', 'Flower', 3.5, 'Fight Club', 'Campfire Cannabis'],
  ...['Cap Junky', 'Mac Stomper', "Mike's Strawberry Lemonade"].map(strain =>
    ['Float Cannabis Co. Float | ' + strain + ' | .75g Pre-Loaded Chillum', '.75g Pre-Loaded Chillum', 'Float Cannabis', 'Flower', .75, strain, 'Float Cannabis']),
  ...['Apple Fritter', 'Cake Mix'].map(strain => ['Redwood County Weed Management ' + strain + ' RCWM 3.5',
    strain + ' RCWM 3.5', 'Redwood County Weed Management', 'Flower', 3.5, strain, 'Redwood County Weed Management']),
  ['Mr. Birch Big Stick Uptown Tart', 'Mr. Birch Big Stick Uptown Tart', 'Verist Fields', 'Preroll', 1, 'Uptown Tart', 'Verist Fields'],
  ['Flor Flor | Royal Girl Scout Cookies | Live Resin | 1g Cartridge | Indica', 'Live Resin', 'FLÖR', 'Vape', 1, 'Royal Girl Scout Cookies', 'FLÖR'],
  ['Unbound Mac V2 5pck #1', 'Mac V2 5pck #1', 'Unbound', 'Flower', 2.5, 'Mac V2', 'Unbound'],
  ['Green Cross Corp Royal Oasis Purple Prince', 'Royal Oasis Purple Prince', 'Green Cross Corp', 'Flower', 3.5, 'Royal Oasis', 'Purple Prince'],
  ['OFFER CONDITIONS APPLY Green Cross Corp Royal Oasis Purple Prince', 'OFFER CONDITIONS APPLY Green Cross Corp Royal Oasis Purple Prince',
    'Green Cross Corp', 'Flower', 3.5, 'Royal Oasis', 'Purple Prince'],
];

for (const [title, rawStrain, maker, category, package_g, strain, brand] of cases) {
  test(title, () => {
    const result = resolve({product_name: title, strain: rawStrain, brand: maker, category, package_g});
    assert.deepEqual(result, {strain, brand});
  });
}
