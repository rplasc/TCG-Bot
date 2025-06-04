CARD_TABLE = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rarity TEXT NOT NULL,
    attack INTEGER,
    defense INTEGER,
    image TEXT
);
"""
