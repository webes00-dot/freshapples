CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY NOT NULL,
  type TEXT NOT NULL,
  retailer_or_strain TEXT,
  source_url TEXT,
  classification TEXT,
  classification_status TEXT,
  details TEXT NOT NULL,
  contact TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
