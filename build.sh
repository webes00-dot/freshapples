#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Reproducible public storefront build from the replacement GitHub repository.
# This script neither reads the original repository nor pulls from a live site.
for js in app.js catalog-model.js brands.js retailers.js map.js reviews.js market-prices.js; do
  node --check "$js"
done

python3 - <<'PY'
import json
from pathlib import Path
required=['site-data.json','catalog.json','brands.json','retailer_locations.json','business_tags.json','review_candidates.json','market-price-history.json']
for name in required:
    obj=json.loads((Path('data')/name).read_text(encoding='utf-8'))
    assert obj is not None,name
site=json.loads(Path('data/site-data.json').read_text())
assert all(x in site for x in ['catalog','retailers','brands']), 'Missing current storefront data'
print('Source data and UI scripts verified.')
PY

rm -rf dist
mkdir -p dist/data
cp index.html brands.html retailers.html map.html reviews.html feedback.html market-prices.html catalog-test.html dist/
cp app.js catalog-model.js brands.js retailers.js map.js reviews.js market-prices.js dist/
cp style.css market-prices.css rcwm-logo.svg market-price-reference.png dist/
cp data/site-data.json data/catalog.json data/brands.json data/retailer_locations.json data/business_tags.json data/review_candidates.json data/market-price-history.json dist/data/
if [ -f data/market-price-monthly.json ]; then
  cp data/market-price-monthly.json dist/data/
fi

python3 - <<'PY'
from pathlib import Path
import hashlib,json
root=Path('dist')
brand_corrections = json.loads(Path('data/listing-brand-corrections.json').read_text())
for name in ('catalog.json', 'site-data.json'):
    path = root / 'data' / name
    payload = json.loads(path.read_text())
    catalog = payload if name == 'catalog.json' else payload['catalog']
    for offer in catalog:
        listing_id = offer.get('id')
        if listing_id in brand_corrections:
            offer['brand'] = brand_corrections[listing_id]
            offer['reviewed_identity'] = True
    path.write_text(json.dumps(payload, ensure_ascii=False) + '\n', encoding='utf-8')
paths=sorted(p for p in root.rglob('*') if p.is_file())
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
Path('dist-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Built',len(paths),'static assets with checksum manifest')
PY
