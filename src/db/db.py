import os
import aiosqlite
from src.models.cards import CARD_TABLE
from src.models.users import USER_TABLE, USER_CARDS_TABLE
from src.models.collections import COLLECTIONS_TABLE

DB_PATH = "data/cards.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CARD_TABLE)
        await db.execute(USER_TABLE)
        await db.execute(USER_CARDS_TABLE)
        await db.execute(COLLECTIONS_TABLE)
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
async def add_card(name, rarity, attack, defense, image, collection_name=None):
    if collection_name:
        collection_id = await get_collection_id(collection_name)
        if not collection_id:
            raise ValueError(f"Collection '{collection_name}' not found.")
    else:
        collection_id = await get_or_create_default_collection()

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO cards (name, rarity, attack, defense, image, collection_id) VALUES (?, ?, ?, ?, ?, ?)",
                (name, rarity, attack, defense, image, collection_id)
            )
            await db.commit()
    except aiosqlite.IntegrityError:
        raise ValueError(f"A card named '{name}' already exists.")
    
# Create a card collection
async def create_collection(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO collections (name) VALUES (?)", (name,))
        await db.commit()

# Get the card collection
async def get_collection_id(name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM collections WHERE name = ?", (name,))
        row = await cursor.fetchone()
        return row[0] if row else None

# Makes sure there is a global collection
async def get_or_create_default_collection():
    await create_collection("Default Collection")
    return await get_collection_id("Default Collection")

# Get card from databse by ID
async def get_card(card_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        return await cursor.fetchone()

# Get card from databse by Name
async def get_card_by_name(name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM cards WHERE LOWER(name) = LOWER(?)", (name,))
        return await cursor.fetchone()
    
# Get cards from database by collection
async def get_cards_by_collection(collection_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.id, cards.name, cards.rarity, cards.attack, cards.defense, cards.image
            FROM cards
            JOIN collections ON cards.collection_id = collections.id
            WHERE LOWER(collections.name) = LOWER(?)
        """, (collection_name,))
        return await cursor.fetchall()
# Get all cards in database
async def get_all_cards():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.id, cards.name, cards.rarity, cards.attack, cards.defense, collections.name
            FROM cards
            LEFT JOIN collections ON cards.collection_id = collections.id
            ORDER BY cards.id ASC
        """)
        return await cursor.fetchall()
