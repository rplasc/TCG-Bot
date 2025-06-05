import os
import datetime
import random
import aiosqlite
from src.models.cards import CARD_TABLE
from src.models.users import USER_TABLE, USER_CARDS_TABLE
from src.models.collections import COLLECTIONS_TABLE
from src.models.daily import DAILY_TABLE
from src.models.progress import COLLECTION_REWARDS_TABLE
from src.models.shop import DAILY_SHOP_TABLE

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
        await db.execute(COLLECTION_REWARDS_TABLE)
        await db.execute(DAILY_SHOP_TABLE)
        await db.commit()

def calculate_level(xp: int) -> int:
    return int((xp / 100) ** 0.5) # quadratic scale for levels

# In-memory cache
_daily_shop_cache = {
    "key": None,
    "cards": []
}

# For manual reset
def clear_daily_shop_cache():
    _daily_shop_cache["date"] = None
    _daily_shop_cache["cards"] = []

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

async def update_xp_and_check_level(user_id: int, xp_gain: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Get current XP and level
        cursor = await db.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return  # user not registered

        old_xp, old_level = row
        new_xp = old_xp + xp_gain
        new_level = calculate_level(new_xp)

        await db.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (new_xp, new_level, user_id))

        if new_level > old_level:
            coins_gained = (new_level - old_level) * 5
            await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (coins_gained, user_id))
            await db.commit()
            return new_level, coins_gained  # Level up occurred

        await db.commit()
        return None, 0  # No level up

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

async def get_card_ids_in_collection(collection_name: str) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.id
            FROM cards
            JOIN collections ON cards.collection_id = collections.id
            WHERE LOWER(collections.name) = LOWER(?)
        """, (collection_name,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_user_owned_card_ids(user_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT card_id FROM user_cards WHERE user_id = ?
        """, (user_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def has_claimed_collection_reward(user_id: int, collection_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM collection_rewards WHERE user_id = ? AND collection_id = ?",
            (user_id, collection_id)
        )
        return await cursor.fetchone() is not None

async def claim_collection_reward(user_id: int, collection_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO collection_rewards (user_id, collection_id) VALUES (?, ?)",
            (user_id, collection_id)
        )
        await db.commit()

async def get_missing_cards_in_collection(user_id: int, collection_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.name
            FROM cards
            JOIN collections ON cards.collection_id = collections.id
            WHERE LOWER(collections.name) = LOWER(?)
            AND cards.id NOT IN (
                SELECT card_id FROM user_cards WHERE user_id = ?
            )
        """, (collection_name, user_id))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def refresh_daily_shop(rotation_key: str, num_cards: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM daily_shop WHERE date != ?", (rotation_key,))
        cursor = await db.execute("SELECT COUNT(*) FROM daily_shop WHERE date = ?", (rotation_key,))
        if (await cursor.fetchone())[0] > 0:
            return  # Already populated

        cursor = await db.execute("SELECT id FROM cards")
        all_card_ids = [row[0] for row in await cursor.fetchall()]
        chosen = random.sample(all_card_ids, min(num_cards, len(all_card_ids)))

        for cid in chosen:
            await db.execute("INSERT INTO daily_shop (card_id, date) VALUES (?, ?)", (cid, rotation_key))
        await db.commit()

def get_shop_rotation_key():
    now = datetime.datetime.now(datetime.timezone.utc)
    rotation_hour = 15  # 3 PM UTC

    if now.hour < rotation_hour:
        rotation_day = now.date() - datetime.timedelta(days=1)
    else:
        rotation_day = now.date()

    return rotation_day.isoformat()

async def get_daily_shop_cards():
    key = get_shop_rotation_key()

    if _daily_shop_cache["key"] == key and _daily_shop_cache["cards"]:
        return _daily_shop_cache["cards"]

    await refresh_daily_shop(key)  # ensure DB matches

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT cards.*
            FROM cards
            JOIN daily_shop ON cards.id = daily_shop.card_id
            WHERE daily_shop.date = ?
        """, (key,))
        cards = await cursor.fetchall()

    _daily_shop_cache["key"] = key
    _daily_shop_cache["cards"] = cards
    return cards

def get_seconds_until_next_rotation():
    now = datetime.datetime.now(datetime.timezone.utc)
    next_rotation = now.replace(hour=15, minute=0, second=0, microsecond=0)
    if now.hour >= 15:
        next_rotation += datetime.timedelta(days=1)
    return (next_rotation - now).total_seconds()

def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"