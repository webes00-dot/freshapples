"""Archive daily medians from fresh observations that agree with the published catalog."""
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from publish_observed import key_of, money, weight

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'data/market-price-history.json'
CENTRAL = ZoneInfo('America/Chicago')
CATEGORIES = {'Flower', 'Preroll', 'Concentrates'}
CARTRIDGE = re.compile(r'\b(?:carts?|cartridges?)\b', re.I)
VAPE = re.compile(r'\bvape\b', re.I)
DISPOSABLE = re.compile(r'\b(?:disposables?|aio|all[- ]in[- ]one)\b', re.I)


def applicable_category(offer):
    category = offer.get('category')
    if category not in CATEGORIES:
        return None
    title = ' '.join(str(offer.get(field) or '') for field in (
        'product_name', 'raw_scanned_product_name', 'product_variant', 'variant',
    ))
    if category == 'Concentrates' and (
        CARTRIDGE.search(title) or (VAPE.search(title) and not DISPOSABLE.search(title))
    ):
        return None
    return category


def archive(history, scan, candidates, catalog):
    if scan.get('limited') or not scan.get('checked_at'):
        return history
    timestamp = scan['checked_at']
    checked = datetime.fromisoformat(timestamp)
    if checked.tzinfo is None:
        raise ValueError('Scan timestamp must include a timezone')
    day = checked.astimezone(CENTRAL).date().isoformat()
    reachable = {status['license'] for status in scan['statuses']
                 if status.get('connection') == 'reachable'}
    current = {}
    conflicting = set()
    for candidate in candidates:
        if candidate.get('checked_at') != timestamp or candidate.get('store_id') not in reachable:
            continue
        key = key_of(candidate)
        observed = (money(candidate.get('price')), weight(candidate.get('package_g')))
        if not key or None in observed:
            continue
        if key in current and current[key] != observed:
            conflicting.add(key)
        current[key] = observed

    prices = defaultdict(list)
    stores = defaultdict(set)
    for offer in catalog:
        category = applicable_category(offer)
        if not category or offer.get('availability_status') == 'coming_soon' or offer.get('size_verification_note'):
            continue
        if offer.get('record_status') == 'advertised_future_menu':
            continue
        source = dict(offer, store_id=offer.get('store_id') or offer.get('retailer_id'),
                      product_name=offer.get('raw_scanned_product_name') or offer.get('product_name'))
        key = key_of(source)
        price = money(offer.get('price'))
        grams = weight(offer.get('package_g'))
        if price is None or grams is None or key in conflicting or current.get(key) != (price, grams):
            continue
        prices[category].append(price / grams)
        stores[category].add(key[0])
        del current[key]

    if not prices:
        return history

    days = dict(history['days'])
    snapshot = dict(days.get(day, {}))
    for category, values in prices.items():
        previous = snapshot.get(category)
        if previous:
            if checked < datetime.fromisoformat(previous['checked_at']):
                continue
            if (len(stores[category]), len(values)) < (previous['retailers'], previous['offers']):
                continue
        snapshot[category] = {
            'median': round(median(values), 2), 'offers': len(values),
            'retailers': len(stores[category]), 'checked_at': timestamp,
        }
    days[day] = snapshot
    return {'version': 1, 'days': days}


def main():
    history = json.loads(HISTORY.read_text())
    if history.get('version') != 1 or not isinstance(history.get('days'), dict):
        raise ValueError('Invalid market price history')
    scan_dir = ROOT / 'collector/data'
    updated = archive(
        history, json.loads((scan_dir / 'latest_scan.json').read_text()),
        json.loads((scan_dir / 'candidate_products.json').read_text()),
        json.loads((ROOT / 'dist/data/catalog.json').read_text()),
    )
    if updated != history:
        output = HISTORY.with_suffix('.tmp')
        output.write_text(json.dumps(updated, indent=2, sort_keys=True) + '\n')
        output.replace(HISTORY)
    print(f"Market price history: {len(updated['days'])} observation dates")


if __name__ == '__main__':
    main()
