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
    get_reward_budget_earned,
    add_reward_budget,
)
from src.utils.time import get_current_date_str
from src.events.service import wager_cap_multiplier
from src.economy.config import (
    CASINO_WAGER_CAPS,
    DAILY_REPEATABLE_COIN_BUDGETS,
    REDUCIBLE_BUDGET_CATEGORIES,
    REPEATABLE_SOFT_CAP_BANDS,
    BUDGET_CASINO_NET,
    tier_for_level,
)


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
    """Return the player's max casino wager based on their tier, scaled by any
    active event wager-cap boost (e.g. High Rollers Week)."""
    tier = await get_player_economy_tier(user_id)
    base = CASINO_WAGER_CAPS.get(tier, CASINO_WAGER_CAPS["new"])
    return int(base * wager_cap_multiplier(game))


def _banded_grant(already: int, base: int, budget: int) -> int:
    """Apply the diminishing-returns bands to `base`, given `already` raw coins
    earned today and the tier `budget`. Bands operate on cumulative raw earnings."""
    if budget <= 0 or base <= 0:
        return base
    granted = 0.0
    pos = float(already)
    remaining = float(base)
    for upper_mult, mult in REPEATABLE_SOFT_CAP_BANDS:
        if remaining <= 0:
            break
        upper = float("inf") if upper_mult is None else upper_mult * budget
        if pos >= upper:
            continue
        take = min(remaining, upper - pos)
        granted += take * mult
        pos += take
        remaining -= take
    return int(granted)


async def apply_repeatable_reward_budget(user_id: int, base_amount: int, category: str) -> int:
    """Reduce a repeatable reward once the player's daily budget is exceeded.

    Returns the coins to actually grant. The full (raw) base is recorded against
    the budget so band thresholds stay stable regardless of the reduction.
    """
    if base_amount <= 0:
        return base_amount
    tier = await get_player_economy_tier(user_id)
    budget = DAILY_REPEATABLE_COIN_BUDGETS.get(tier, DAILY_REPEATABLE_COIN_BUDGETS["new"])
    date = get_current_date_str()
    already = await get_reward_budget_earned(user_id, date, REDUCIBLE_BUDGET_CATEGORIES)
    granted = _banded_grant(already, base_amount, budget)
    await add_reward_budget(user_id, date, category, base_amount)
    return granted


async def record_casino_net(user_id: int, net: int) -> None:
    """Track daily casino net winnings for telemetry (does not reduce payouts)."""
    await add_reward_budget(user_id, get_current_date_str(), BUDGET_CASINO_NET, net)
