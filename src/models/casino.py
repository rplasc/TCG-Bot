CASINO_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS casino_stats (
    user_id INTEGER PRIMARY KEY,
    games_played INTEGER DEFAULT 0,
    coins_wagered INTEGER DEFAULT 0,
    coins_paid_out INTEGER DEFAULT 0,
    biggest_win INTEGER DEFAULT 0,
    blackjack_wins INTEGER DEFAULT 0,
    slot_jackpots INTEGER DEFAULT 0,
    roulette_wins INTEGER DEFAULT 0,
    updated_at TEXT
);
"""
