import os
import aiosqlite
from src.models.cards import CARD_TABLE
from src.models.users import USER_TABLE, USER_CARDS_TABLE

DB_PATH = "data/cards.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CARD_TABLE)
        await db.execute(USER_TABLE)
        await db.execute(USER_CARDS_TABLE)
        await db.commit()

# Add user to db
async def register_user(user_id, name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user_id, name))
        await db.commit()

# Add card to user collection
async def add_to_user_collection(user_id, card_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Try to update quantity
        result = await db.execute(
            "UPDATE user_cards SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?",
            (user_id, card_id)
        )
        if result.rowcount == 0:
            # If no row updated, insert new
            await db.execute(
                "INSERT INTO user_cards (user_id, card_id, quantity) VALUES (?, ?, 1)",
                (user_id, card_id)
            )
        await db.commit()

# Pull a user's collection
async def get_user_collection(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.id, cards.name, cards.rarity, cards.image, user_cards.quantity
            FROM user_cards
            JOIN cards ON user_cards.card_id = cards.id
            WHERE user_cards.user_id = ?
        """, (user_id,))
        return await cursor.fetchall()

# Add card to database
async def add_card(name, rarity, attack, defense, image):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO cards (name, rarity, attack, defense, image) VALUES (?, ?, ?, ?, ?)",
            (name, rarity, attack, defense, image)
        )
        await db.commit()

# Get card from databse
async def get_card(card_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        return await cursor.fetchone()
