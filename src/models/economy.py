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

DAILY_REWARD_BUDGETS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_reward_budgets (
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_earned INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date, category)
);
"""
