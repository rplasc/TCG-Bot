import os
import aiosqlite
from src.models.cards import CARD_TABLE

DB_PATH = "data/cards.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CARD_TABLE)
        await db.commit()

async def add_card(name, rarity, attack, defense, image):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO cards (name, rarity, attack, defense, image) VALUES (?, ?, ?, ?, ?)",
            (name, rarity, attack, defense, image)
        )
        await db.commit()

async def get_card(card_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        return await cursor.fetchone()
