CURRENCY_LEDGER_TABLE = """
CREATE TABLE IF NOT EXISTS currency_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);
"""
