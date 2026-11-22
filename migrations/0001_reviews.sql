CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, brand TEXT NOT NULL, strain TEXT NOT NULL, product_type TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), body TEXT NOT NULL, reddit_handle TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('published','hidden','removed')), ip_hash TEXT);
CREATE INDEX IF NOT EXISTS idx_reviews_lookup ON reviews(brand,strain,status,created_at);
CREATE TABLE IF NOT EXISTS review_flags (id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id), reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), ip_hash TEXT);
CREATE INDEX IF NOT EXISTS idx_review_flags_review ON review_flags(review_id);
