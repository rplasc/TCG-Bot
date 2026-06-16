from src.database.db import can_afford
from src.economy.service import get_max_wager

MIN_CASINO_WAGER = 5
# Absolute ceiling fallback. The effective max is per-level (see get_max_wager).
MAX_CASINO_WAGER = 1000
DEFAULT_SLOT_WAGERS = [5, 25, 100]


async def max_wager_for(user_id: int, game: str = "casino") -> int:
    """The player's effective max wager based on their level tier."""
    return await get_max_wager(user_id, game)


async def validate_wager(user_id: int, raw_amount: str, game: str = "casino") -> tuple[bool, int | str]:
    try:
        amount = int(raw_amount)
    except (ValueError, TypeError):
        return False, "❌ Please enter a valid whole number."

    if amount <= 0:
        return False, "❌ Wager must be greater than zero."
    if amount < MIN_CASINO_WAGER:
        return False, f"❌ Minimum wager is {MIN_CASINO_WAGER} coins."

    cap = min(await max_wager_for(user_id, game), MAX_CASINO_WAGER)
    if amount > cap:
        return False, f"❌ Your max wager is {cap} coins at your level."
    if not await can_afford(user_id, amount):
        return False, "❌ You don't have enough coins."

    return True, amount
