USER_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
"""

USER_CARDS_TABLE = """
CREATE TABLE IF NOT EXISTS user_cards (
    user_id INTEGER,
    card_id INTEGER,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);
"""
