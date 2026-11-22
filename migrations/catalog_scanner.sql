CREATE TABLE IF NOT EXISTS scanner_offers (
    offer_key TEXT PRIMARY KEY,
    retailer_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    public_json TEXT NOT NULL
);
