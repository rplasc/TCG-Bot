SPORTS_MATCHES_TABLE = """
CREATE TABLE IF NOT EXISTS sports_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_day TEXT UNIQUE NOT NULL,
    team_a TEXT NOT NULL,
    team_b TEXT NOT NULL,
    strength_a REAL NOT NULL,
    strength_b REAL NOT NULL,
    seed_a INTEGER NOT NULL,
    seed_b INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    winner TEXT,
    created_at TEXT,
    settled_at TEXT
);
"""

SPORTS_BETS_TABLE = """
CREATE TABLE IF NOT EXISTS sports_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    side TEXT NOT NULL,
    amount INTEGER NOT NULL,
    created_at TEXT
);
"""

SPORTS_BETS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sports_bets_match_side
    ON sports_bets (match_id, side);
"""
