#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

assets=(
  index.html brands.html retailers.html map.html market-prices.html reviews.html feedback.html
  app.js catalog-model.js brands.js retailers.js map.js market-prices.js reviews.js
  style.css market-prices.css rcwm-logo.svg market-price-reference.png
)

for asset in "${assets[@]}"; do
  if [[ "$asset" == *.js ]]; then
    node --check "$asset"
  fi
done

python3 scripts/build_public_snapshot.py
cp "${assets[@]}" dist/

python3 - <<'PY'
import hashlib
import re
from pathlib import Path

for page, script in (
    ('index.html', 'catalog-model.js'), ('index.html', 'app.js'),
    ('retailers.html', 'retailers.js'), ('brands.html', 'brands.js'),
    ('brands.html', 'catalog-model.js'), ('map.html', 'map.js'),
):
    html = Path('dist', page)
    digest = hashlib.sha256(Path('dist', script).read_bytes()).hexdigest()[:12]
    pattern = r'(src="' + re.escape(script) + r')(?:\?v=[^"]*)?(")'
    content, count = re.subn(pattern, lambda m: m[1] + '?v=' + digest + m[2], html.read_text())
    if count != 1:
        raise ValueError(f'Missing unique {script} reference in {page}')
    html.write_text(content)
PY
