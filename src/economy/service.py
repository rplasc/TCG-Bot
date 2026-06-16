"""Economy service: ledger-aware wrappers around the raw coin helpers.

These wrap the existing `src.database.db` helpers and additionally record a row in
`currency_ledger`. Systems that have not yet been migrated keep calling the raw
helpers directly and simply don't log — wiring them up is a later phase.
"""

import json
import uuid

from src.database.db import (
    give_coins,
    deduct_coins,
    get_balance,
    get_level,
    insert_ledger_entry,
)
from src.economy.config import CASINO_WAGER_CAPS, tier_for_level


def _dump_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    return json.dumps(metadata, default=str)


async def award_coins(user_id: int, amount: int, source: str, metadata: dict | None = None) -> int:
    """Give coins and record a positive ledger entry. Returns the new balance."""
    await give_coins(user_id, amount)
    balance = await get_balance(user_id)
    await insert_ledger_entry(user_id, amount, balance, source, None, _dump_metadata(metadata))
    return balance


async def spend_coins(user_id: int, amount: int, source: str, metadata: dict | None = None) -> bool:
    """Deduct coins and, on success, record a negative ledger entry."""
    ok = await deduct_coins(user_id, amount)
    if not ok:
        return False
    balance = await get_balance(user_id)
    await insert_ledger_entry(user_id, -amount, balance, source, None, _dump_metadata(metadata))
    return True


async def transfer_coins(
    from_user_id: int,
    to_user_id: int,
    amount: int,
    source: str,
    metadata: dict | None = None,
) -> bool:
    """Move coins between players as a matched debit/credit sharing a source_id."""
    if not await deduct_coins(from_user_id, amount):
        return False
    await give_coins(to_user_id, amount)
    source_id = uuid.uuid4().hex
    meta = _dump_metadata(metadata)
    from_balance = await get_balance(from_user_id)
    to_balance = await get_balance(to_user_id)
    await insert_ledger_entry(from_user_id, -amount, from_balance, source, source_id, meta)
    await insert_ledger_entry(to_user_id, amount, to_balance, source, source_id, meta)
    return True


async def get_player_economy_tier(user_id: int) -> str:
    return tier_for_level(await get_level(user_id))


async def get_max_wager(user_id: int, game: str = "casino") -> int:
    """Return the player's max casino wager based on their tier."""
    tier = await get_player_economy_tier(user_id)
    return CASINO_WAGER_CAPS.get(tier, CASINO_WAGER_CAPS["new"])
