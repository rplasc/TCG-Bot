DAILY_TABLE = """
CREATE TABLE IF NOT EXISTS daily_cooldowns (
    user_id INTEGER PRIMARY KEY,
    last_claimed TEXT
);
"""