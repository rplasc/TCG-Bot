USER_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    coins INTEGER DEFAULT 35,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    rp INTEGER DEFAULT 0,
    rank INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0
);
"""

USER_CARDS_TABLE = """
CREATE TABLE IF NOT EXISTS user_cards (
    user_id INTEGER,
    card_id INTEGER,
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);
"""
