import os
import datetime
import aiosqlite
from src.models.cards import CARD_TABLE
from src.models.users import USER_TABLE, USER_CARDS_TABLE
from src.models.collections import COLLECTIONS_TABLE
from src.models.daily import DAILY_TABLE

DB_PATH = "data/cards.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CARD_TABLE)
        await db.execute(USER_TABLE)
        await db.execute(USER_CARDS_TABLE)
        await db.execute(COLLECTIONS_TABLE)
        await db.execute(DAILY_TABLE)
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
            SELECT cards.id, cards.name, cards.rarity, cards.attack, cards.defense, cards.hp, cards.image
            FROM user_cards
            JOIN cards ON user_cards.card_id = cards.id
            WHERE user_cards.user_id = ?
        """, (user_id,))
        return await cursor.fetchall()

# Add card to database
async def add_card(name, rarity, attack, defense, hp, image, collection_name=None):
    if collection_name:
        collection_id = await get_collection_id(collection_name)
        if not collection_id:
            raise ValueError(f"Collection '{collection_name}' not found.")
    else:
        collection_id = await get_or_create_default_collection()

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO cards (name, rarity, attack, defense, hp, image, collection_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, rarity, attack, defense, hp, image, collection_id)
            )
            await db.commit()
    except aiosqlite.IntegrityError:
        raise ValueError(f"A card named '{name}' already exists.")
    
# Delete a card from database by name
async def delete_card_by_name(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM cards WHERE LOWER(name) = LOWER(?)", (name,))
        await db.commit()
        return cursor.rowcount > 0
    
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

# Deletes a collection by name
async def delete_collection_by_name(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM collections WHERE LOWER(name) = LOWER(?)", (name,))
        await db.commit()
        return cursor.rowcount > 0

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
            SELECT cards.id, cards.name, cards.rarity, cards.attack, cards.defense, cards.hp, cards.image
            FROM cards
            JOIN collections ON cards.collection_id = collections.id
            WHERE LOWER(collections.name) = LOWER(?)
        """, (collection_name,))
        return await cursor.fetchall()
    
# Get all cards in database
async def get_all_cards():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.id, cards.name, cards.rarity, cards.attack, cards.defense, cards.hp, collections.name
            FROM cards
            LEFT JOIN collections ON cards.collection_id = collections.id
            ORDER BY cards.id ASC
        """)
        return await cursor.fetchall()

async def get_balance(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_balance(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = ? WHERE id = ?", (amount, user_id))
        await db.commit()

async def give_coins(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (amount, user_id))
        await db.commit()

async def can_afford(user_id: int, cost: int) -> bool:
    balance = await get_balance(user_id)
    return balance is not None and balance >= cost

async def deduct_coins(user_id: int, cost: int) -> bool:
    if await can_afford(user_id, cost):
        await set_balance(user_id, (await get_balance(user_id)) - cost)
        return True
    return False

async def has_claimed_today(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_claimed FROM daily_cooldowns WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return False
        last_claim = datetime.datetime.fromisoformat(row[0])
        return last_claim.date() == datetime.datetime.now(datetime.timezone.utc).date()

async def update_daily_claim(user_id: int):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO daily_cooldowns (user_id, last_claimed) VALUES (?, ?)", (user_id, now))
        await db.commit()

async def get_xp(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT xp FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def add_xp(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (amount, user_id))
        await db.commit()

async def get_top_users_by_xp(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name, xp FROM users ORDER BY xp DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

async def update_card_by_name(name, *, attack=None, defense=None, hp=None, image=None, rarity=None, collection_name=None):
    async with aiosqlite.connect(DB_PATH) as db:
        updates = []
        params = []

        if attack is not None:
            updates.append("attack = ?")
            params.append(attack)
        if defense is not None:
            updates.append("defense = ?")
            params.append(defense)
        if hp is not None:
            updates.append("hp = ?")
            params.append(hp)
        if image is not None:
            updates.append("image = ?")
            params.append(image)
        if rarity is not None:
            updates.append("rarity = ?")
            params.append(rarity)
        if collection_name is not None:
            collection_id = await get_collection_id(collection_name)
            if not collection_id:
                raise ValueError(f"Collection '{collection_name}' not found.")
            updates.append("collection_id = ?")
            params.append(collection_id)

        if not updates:
            raise ValueError("No fields provided to update.")

        params.append(name)
        await db.execute(f"UPDATE cards SET {', '.join(updates)} WHERE LOWER(name) = LOWER(?)", params)
        await db.commit()

async def user_owns_card(user_id: int, card_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?
        """, (user_id, card_id))
        return await cursor.fetchone() is not None
