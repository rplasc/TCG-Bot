CARD_TABLE = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    rarity TEXT NOT NULL,
    attack INTEGER,
    defense INTEGER,
    hp INTEGER,
    image TEXT,
    collection_id INTEGER,
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);
"""
