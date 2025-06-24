DAILY_TABLE = """
CREATE TABLE IF NOT EXISTS daily_cooldowns (
    user_id INTEGER PRIMARY KEY,
    last_claimed TEXT,
    current_streak INTEGER DEFAULT 0,
    streak_updated TEXT
);
"""