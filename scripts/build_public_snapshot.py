"""Build the pre-V2 website's data files from its archived public records."""

import gzip
import json
from collections import defaultdict
from hashlib import sha256
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit


def read(name):
    return json.loads(Path('data', name).read_text(encoding='utf-8'))


def stable_id(values):
    return sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()[:24]


def public_url(value):
    url = urlsplit(value)
    return url.scheme in ('http', 'https') and url.hostname and not (url.username or url.password)


def build_preserved_snapshot(path):
    with gzip.open(path, 'rt', encoding='utf-8') as archive:
        preserved = json.load(archive)
    data = preserved['site-data']
    offers = data['catalog']
    if data['schema_version'] != 1 or not offers or not data['strain_genetics'] or not data['strain_types']:
        raise ValueError('The preserved production snapshot is incomplete')
    if any(not row.get('id') for row in offers) or len({row['id'] for row in offers}) != len(offers):
        raise ValueError('The preserved catalog has invalid listing identifiers')
    coordinates = read('verified-retailer-coordinates.json')
    for retailer in data['retailers']:
        verified = coordinates.get(retailer['id'])
        address = retailer.get('map_address') or retailer.get('address')
        if verified and verified['coordinate_for_address'] == address:
            retailer.update(verified)
    data['manifest'].update({
        'data_source': 'Preserved production menu snapshot',
        'listings': len(offers),
        'automated_scans_running': False,
    })
    output = Path('dist/data')
    output.mkdir(parents=True, exist_ok=True)
    for name, value in {
        'site-data': data,
        'catalog': offers,
        'brands': data['brands'],
        'business_tags': data['business_tags'],
        'retailer_locations': data['retailers'],
        'review_candidates': preserved['review_candidates'],
        'market-price-history': preserved['market-price-history'],
    }.items():
        (output / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Preserved {len(offers)} production offers and {len(data["strain_genetics"])} strain profiles')


def build():
    preserved = Path('data/published-site-baseline.json.gz')
    if preserved.is_file():
        build_preserved_snapshot(preserved)
        return

    stores = read('public-retailer-directory.json')['retailers']
    offers = read('public-menu-observations.json')['offers']
    enrichment = read('public-site-enrichment.json')
    if not stores or not offers:
        raise ValueError('An archived public directory and catalog are required')

    directories = defaultdict(list)
    retailer_tags = []
    store_enrichment = {(row['name'], row['address']): row for row in enrichment['retailers']}
    for store in stores:
        if not store['name'] or not store['address']:
            raise ValueError('Retailer is missing a name or address')
        if any(not public_url(store[key]) for key in ('website_url', 'menu_url') if key in store):
            raise ValueError(f'Invalid public link for {store["name"]}')
        identity = store['name'], store['address']
        store['id'] = stable_id(identity)
        store['status'] = 'menu_link_prior_audit' if store.get('menu_url') else 'website_only'
        extra = store_enrichment.get(identity, {})
        store.update(extra.get('map', {}))
        if extra.get('tags'):
            retailer_tags.append({'id': store['id'], 'name': store['name'], **extra['tags']})
        directories[store['name'].casefold()].append(store)

    brands = {}
    for offer in offers:
        price = offer['price']
        if not isfinite(price) or price <= 0 or not public_url(offer['url']):
            raise ValueError(f'Invalid public offer for {offer["product_name"]}')
        offer['id'] = stable_id([offer.get(key) for key in (
            'retailer', 'url', 'product_name', 'brand', 'strain', 'category', 'package_g',
        )])
        offer['stock_status'] = 'not_verified'
        matches = directories[offer['retailer'].casefold()]
        if len(matches) == 1:
            offer['retailer_id'] = matches[0]['id']
            matches[0]['status'] = 'third_party_priced_menu_observed'
        if offer.get('brand'):
            brands.setdefault(offer['brand'].casefold(), {'name': offer['brand']})

    for records in (stores, offers):
        if len({record['id'] for record in records}) != len(records):
            raise ValueError('Duplicate identities in public snapshot')

    payload = {
        'schema_version': 1,
        'catalog': offers,
        'retailers': stores,
        'brands': list(brands.values()),
        'business_tags': {'brands': enrichment['brand_tags'], 'retailers': retailer_tags},
        'strain_types': {},
        'strain_genetics': [],
        'rcwm_strains': enrichment['rcwm_strains'],
        'manifest': {'data_source': 'Archived public menu observations', 'listings': len(offers)},
    }
    output = Path('dist/data')
    output.mkdir(parents=True, exist_ok=True)
    for name, value in {
        'site-data': payload,
        'catalog': offers,
        'brands': payload['brands'],
        'business_tags': payload['business_tags'],
        'retailer_locations': stores,
        'review_candidates': {'candidates': []},
        'market-price-history': {'version': 1, 'days': {}},
    }.items():
        (output / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Public preview built with {len(offers)} offers, {len(stores)} locations, and {len(brands)} brands')


if __name__ == '__main__':
    build()
