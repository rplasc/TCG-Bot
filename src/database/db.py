import os
import datetime
import zoneinfo
import random
import aiosqlite
from typing import Tuple
from src.models.cards import CARD_TABLE
from src.models.users import USER_TABLE, USER_CARDS_TABLE
from src.models.collections import COLLECTIONS_TABLE
from src.models.daily import DAILY_TABLE
from src.models.progress import COLLECTION_REWARDS_TABLE
from src.models.shop import DAILY_SHOP_TABLE
from src.models.casino import CASINO_STATS_TABLE
from src.models.economy import CURRENCY_LEDGER_TABLE, DAILY_REWARD_BUDGETS_TABLE
from src.models.events import EVENT_STATE_TABLE
from src.economy.config import DAILY_CLAIM, DAILY_STREAK_BONUS, LEVEL_UP_REWARD

from src.utils.ranks import calculate_user_rank
from src.utils.levels import calculate_level
from src.utils.time import get_shop_rotation_key, get_current_date_str,is_consecutive_day, is_same_day, get_streak_bonus
from src.events.service import apply_xp, coin_multiplier

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
        await db.execute(CASINO_STATS_TABLE)
        await db.execute(CURRENCY_LEDGER_TABLE)
        await db.execute(DAILY_REWARD_BUDGETS_TABLE)
        await db.execute(EVENT_STATE_TABLE)
        await db.commit()


async def get_last_announced_event_key() -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_announced_key FROM event_state WHERE id = 1")
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_last_announced_event_key(key: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO event_state (id, last_announced_key) VALUES (1, ?)",
            (key,),
        )
        await db.commit()

# In-memory cache
_daily_shop_cache = {
    "key": None,
    "cards": []
}

# For manual reset
def clear_daily_shop_cache():
    _daily_shop_cache["key"] = None
    _daily_shop_cache["cards"] = []

# Add user to db
async def register_user(user_id, name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user_id, name))
        await db.commit()

# Add card to user collection
async def add_to_user_collection(user_id, card_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO user_cards (user_id, card_id)
            VALUES (?, ?)
        """, (user_id, card_id))
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
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0
    except aiosqlite.Error as e:
        print(f"Database error in get_balance: {e}")
        return 0

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

async def update_casino_stats(
    user_id: int,
    *,
    wager: int = 0,
    payout: int = 0,
    blackjack_win: bool = False,
    slot_jackpot: bool = False,
    roulette_win: bool = False,
):
    net = payout - wager
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO casino_stats (user_id, games_played, coins_wagered, coins_paid_out, biggest_win,
                blackjack_wins, slot_jackpots, roulette_wins, updated_at)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                games_played    = games_played + 1,
                coins_wagered   = coins_wagered + excluded.coins_wagered,
                coins_paid_out  = coins_paid_out + excluded.coins_paid_out,
                biggest_win     = MAX(biggest_win, excluded.biggest_win),
                blackjack_wins  = blackjack_wins + excluded.blackjack_wins,
                slot_jackpots   = slot_jackpots + excluded.slot_jackpots,
                roulette_wins   = roulette_wins + excluded.roulette_wins,
                updated_at      = excluded.updated_at
            """,
            (
                user_id,
                wager,
                payout,
                max(net, 0),
                int(blackjack_win),
                int(slot_jackpot),
                int(roulette_win),
                now,
            ),
        )
        await db.commit()


async def deduct_coins(user_id: int, cost: int) -> bool:
    if await can_afford(user_id, cost):
        await set_balance(user_id, (await get_balance(user_id)) - cost)
        return True
    return False

async def get_last_daily_claim(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_claimed FROM daily_cooldowns WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def update_daily_claim(user_id: int):
    now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles")).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO daily_cooldowns (user_id, last_claimed) VALUES (?, ?)", (user_id, now))
        await db.commit()

async def get_xp(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT xp FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_level(user_id) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT level FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def insert_ledger_entry(user_id, amount, balance_after, source, source_id=None, metadata_json=None):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO currency_ledger
                (user_id, amount, balance_after, source, source_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, amount, balance_after, source, source_id, metadata_json, now),
        )
        await db.commit()

async def get_reward_budget_earned(user_id, date, categories) -> int:
    """Sum amount_earned for the given categories on a date."""
    if not categories:
        return 0
    placeholders = ",".join("?" for _ in categories)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"""
            SELECT COALESCE(SUM(amount_earned), 0) FROM daily_reward_budgets
            WHERE user_id = ? AND date = ? AND category IN ({placeholders})
            """,
            (user_id, date, *categories),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def add_reward_budget(user_id, date, category, amount):
    """Add to the running amount_earned for (user, date, category)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO daily_reward_budgets (user_id, date, category, amount_earned)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, date, category) DO UPDATE SET
                amount_earned = amount_earned + excluded.amount_earned
            """,
            (user_id, date, category, amount),
        )
        await db.commit()

async def get_recent_ledger(user_id, limit=10):
    """Most recent ledger entries for a user: (amount, balance_after, source, created_at)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT amount, balance_after, source, created_at FROM currency_ledger
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        )
        return await cursor.fetchall()

async def get_ledger_source_totals(user_id=None):
    """Per-source totals: (source, total_amount, entry_count). Global if user_id is None."""
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id is None:
            cursor = await db.execute(
                "SELECT source, SUM(amount), COUNT(*) FROM currency_ledger GROUP BY source ORDER BY SUM(amount)"
            )
        else:
            cursor = await db.execute(
                "SELECT source, SUM(amount), COUNT(*) FROM currency_ledger WHERE user_id = ? GROUP BY source ORDER BY SUM(amount)",
                (user_id,),
            )
        return await cursor.fetchall()

async def get_economy_totals(user_id=None):
    """Return (coins_created, coins_destroyed) where destroyed is a positive number."""
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id is None:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount END),0), "
                "COALESCE(SUM(CASE WHEN amount < 0 THEN amount END),0) FROM currency_ledger"
            )
        else:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount END),0), "
                "COALESCE(SUM(CASE WHEN amount < 0 THEN amount END),0) FROM currency_ledger WHERE user_id = ?",
                (user_id,),
            )
        created, destroyed = await cursor.fetchone()
        return created, -destroyed

async def get_user_budgets(user_id, date):
    """Daily budget rows for a user on a date: (category, amount_earned)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT category, amount_earned FROM daily_reward_budgets WHERE user_id = ? AND date = ? ORDER BY category",
            (user_id, date),
        )
        return await cursor.fetchall()

async def _insert_ledger_tx(db, user_id, amount, balance_after, source, source_id=None, metadata_json=None):
    """Write a ledger row using an already-open transaction (no commit)."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO currency_ledger
            (user_id, amount, balance_after, source, source_id, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, amount, balance_after, source, source_id, metadata_json, now),
    )

async def update_xp_and_check_level(user_id: int, xp_gain: int):
    # Apply any active event XP multiplier (no-op when no event is active).
    xp_gain = apply_xp(xp_gain)
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            # Start transaction
            await db.execute("BEGIN")
            
            # Get current stats
            cursor = await db.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                await db.execute("ROLLBACK")
                return None, 0
            
            old_xp, old_level = row
            new_xp = old_xp + xp_gain
            new_level = calculate_level(new_xp)
            
            # Update XP and level
            await db.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", 
                            (new_xp, new_level, user_id))
            
            # Award coins if leveled up
            if new_level > old_level:
                coins_gained = (new_level - old_level) * 5
                await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?",
                                (coins_gained, user_id))
                cursor = await db.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
                balance_after = (await cursor.fetchone())[0]
                await _insert_ledger_tx(db, user_id, coins_gained, balance_after, LEVEL_UP_REWARD,
                                        None, f'{{"new_level": {new_level}}}')
                await db.commit()
                return new_level, coins_gained
            
            await db.commit()
            return None, 0
            
        except Exception as e:
            await db.execute("ROLLBACK")
            raise e
        
async def get_top_users_by_xp(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name, xp FROM users ORDER BY xp DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()
    
async def get_top_users_by_rank(limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name, rank, wins FROM users ORDER BY rank DESC, wins DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

async def get_user_rank_position(user_id):
    """Return (position, rank, wins) for a user using the leaderboard ordering,
    or None if the user has no row. ``position`` is 1-based."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT rank, wins FROM users WHERE id = ?", (user_id,))
        me = await cursor.fetchone()
        if not me:
            return None
        rank, wins = me
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE rank > ? OR (rank = ? AND wins > ?)",
            (rank, rank, wins)
        )
        ahead = (await cursor.fetchone())[0]
        return ahead + 1, rank, wins

async def get_all_collection_names():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM collections ORDER BY name ASC")
        return [row[0] for row in await cursor.fetchall()]

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
            AND NOT EXISTS (
                SELECT 1 FROM user_cards 
                WHERE user_cards.card_id = cards.id 
                AND user_cards.user_id = ?
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

async def remove_from_user_collection(user_id: int, card_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM user_cards
            WHERE rowid = (
                SELECT rowid FROM user_cards
                WHERE user_id = ? AND card_id = ?
                LIMIT 1
            )
        """, (user_id, card_id))
        await db.commit()

async def get_rank_id(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT rank FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0
    
async def get_rp(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT rp, rank FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return
        return row[0] if row else 0

async def update_rp_and_check_rank(user_id: int, rp_gain: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT rp, rank FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return

        old_rp, old_rank = row
        new_rp = old_rp + rp_gain
        new_rp, new_rank = calculate_user_rank(new_rp, old_rank)

        await db.execute("UPDATE users SET rp = ?, rank = ? WHERE id = ?", (new_rp, new_rank, user_id))

        if new_rank != old_rank:
            await db.commit()
            return new_rank

        await db.commit()
        return None

async def add_win(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET wins = wins + 1 WHERE id = ?", (user_id,))
        await db.commit()

async def get_wins(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT wins FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_user_streak_info(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT last_claimed, current_streak, streak_updated
            FROM daily_cooldowns 
            WHERE user_id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        
        if not row:
            return {
                'last_claimed': None,
                'current_streak': 0,
                'streak_updated': None
            }
        
        return {
            'last_claimed': row[0],
            'current_streak': row[1] or 0,
            'streak_updated': row[2]
        }

async def can_claim_daily_reward(user_id: int) -> Tuple[bool, dict]:
    streak_info = await get_user_streak_info(user_id)
    current_date = get_current_date_str()
    
    if not streak_info['last_claimed']:
        return True, streak_info
    
    last_claimed_date = streak_info['last_claimed'][:10]
    
    if is_same_day(last_claimed_date, current_date):
        return False, streak_info
    
    return True, streak_info

async def claim_daily_reward_with_streak(user_id: int) -> dict:
    can_claim, streak_info = await can_claim_daily_reward(user_id)
    
    if not can_claim:
        return {
            'success': False,
            'message': 'Daily reward already claimed today',
            'streak_info': streak_info
        }
    
    current_date = get_current_date_str()
    current_datetime = datetime.datetime.now().isoformat()
    
    new_streak = 1
    if streak_info['last_claimed']:
        last_claimed_date = streak_info['last_claimed'][:10]
        
        if is_consecutive_day(last_claimed_date, current_date):
            new_streak = streak_info['current_streak'] + 1
        
    # Calculate rewards (scaled by any active event coin multiplier)
    coin_mult = coin_multiplier()
    base_coins = int(round(15 * coin_mult))
    bonus_coins = int(round(get_streak_bonus(new_streak) * coin_mult))
    total_coins = base_coins + bonus_coins
    
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN")
            
            await db.execute("""
                INSERT OR REPLACE INTO daily_cooldowns 
                (user_id, last_claimed, current_streak, streak_updated)
                VALUES (?, ?, ?, ?)
            """, (user_id, current_datetime, new_streak, current_datetime))
            
            await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (total_coins, user_id))
            cursor = await db.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
            final_balance = (await cursor.fetchone())[0]
            await _insert_ledger_tx(db, user_id, base_coins, final_balance - bonus_coins, DAILY_CLAIM)
            if bonus_coins > 0:
                await _insert_ledger_tx(db, user_id, bonus_coins, final_balance, DAILY_STREAK_BONUS,
                                        None, f'{{"streak": {new_streak}}}')
            await db.commit()

            return {
                'success': True,
                'base_coins': base_coins,
                'bonus_coins': bonus_coins,
                'total_coins': total_coins,
                'current_streak': new_streak,
                'streak_broken': new_streak == 1 and streak_info['current_streak'] > 1,
            }
            
        except Exception as e:
            await db.execute("ROLLBACK")
            raise e

async def update_xp_and_check_level_in_transaction(db, user_id: int, xp_gain: int):
    cursor = await db.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    
    if not row:
        return None
    
    old_xp, old_level = row
    new_xp = old_xp + xp_gain
    new_level = calculate_level(new_xp)
    await db.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (new_xp, new_level, user_id))
    
    if new_level > old_level:
        coins_gained = (new_level - old_level) * 5
        await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (coins_gained, user_id))
        cursor = await db.execute("SELECT coins FROM users WHERE id = ?", (user_id,))
        balance_after = (await cursor.fetchone())[0]
        await _insert_ledger_tx(db, user_id, coins_gained, balance_after, LEVEL_UP_REWARD,
                                None, f'{{"new_level": {new_level}}}')
        return {'new_level': new_level, 'coins_gained': coins_gained}

    return None