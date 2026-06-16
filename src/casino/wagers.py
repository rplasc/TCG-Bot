from src.database.db import can_afford

MIN_CASINO_WAGER = 5
MAX_CASINO_WAGER = 500
DEFAULT_SLOT_WAGERS = [5, 25, 100]


async def validate_wager(user_id: int, raw_amount: str) -> tuple[bool, int | str]:
    try:
        amount = int(raw_amount)
    except (ValueError, TypeError):
        return False, "❌ Please enter a valid whole number."

    if amount <= 0:
        return False, "❌ Wager must be greater than zero."
    if amount < MIN_CASINO_WAGER:
        return False, f"❌ Minimum wager is {MIN_CASINO_WAGER} coins."
    if amount > MAX_CASINO_WAGER:
        return False, f"❌ Maximum wager is {MAX_CASINO_WAGER} coins."
    if not await can_afford(user_id, amount):
        return False, "❌ You don't have enough coins."

    return True, amount
