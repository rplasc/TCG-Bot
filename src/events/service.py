"""Combined event-effect accessors.

These are the only functions the rest of the bot calls. They merge the currently
active daily and weekly events into a single effect value. All functions are
synchronous and side-effect free, so they're cheap to call from hot paths like
casino spins and pack pulls.
"""

from src.events.config import EventDef
from src.events.schedule import active_daily, active_weekly


def active_events() -> list[EventDef]:
    return [e for e in (active_daily(), active_weekly()) if e]


def _product(attr: str) -> float:
    m = 1.0
    for e in active_events():
        m *= getattr(e.effects, attr)
    return m


def _product_for_game(attr: str, game: str) -> float:
    m = 1.0
    for e in active_events():
        if not e.effects.casino_games or game in e.effects.casino_games:
            m *= getattr(e.effects, attr)
    return m


def coin_multiplier() -> float:
    return _product("coin_mult")


def xp_multiplier() -> float:
    return _product("xp_mult")


def casino_payout_multiplier(game: str) -> float:
    return _product_for_game("casino_payout_mult", game)


def wager_cap_multiplier(game: str) -> float:
    return _product_for_game("wager_cap_mult", game)


def shop_discount() -> float:
    """Additive across active events, clamped to a safe maximum."""
    total = sum(e.effects.shop_discount for e in active_events())
    return min(total, 0.5)


def drop_pool_override(base_pool: dict) -> dict:
    """Return the first active event's drop-pool override, else the base pool."""
    for e in active_events():
        if e.effects.drop_pool:
            return e.effects.drop_pool
    return base_pool


def format_effects(event: EventDef) -> str:
    """Human-readable one-line summary of an event's effects."""
    e = event.effects
    parts: list[str] = []
    if e.coin_mult != 1.0:
        parts.append(f"Coins ×{e.coin_mult:g}")
    if e.xp_mult != 1.0:
        parts.append(f"XP ×{e.xp_mult:g}")
    if e.casino_payout_mult != 1.0:
        scope = "/".join(e.casino_games) if e.casino_games else "all games"
        parts.append(f"Casino payouts ×{e.casino_payout_mult:g} ({scope})")
    if e.wager_cap_mult != 1.0:
        scope = "/".join(e.casino_games) if e.casino_games else "all games"
        parts.append(f"Wager caps ×{e.wager_cap_mult:g} ({scope})")
    if e.shop_discount:
        parts.append(f"{int(e.shop_discount * 100)}% shop discount")
    if e.drop_pool:
        parts.append("Boosted drop rates")
    return " · ".join(parts) if parts else "No active effects"


def apply_coins(base: int) -> int:
    return int(round(base * coin_multiplier()))


def apply_xp(base: int) -> int:
    return int(round(base * xp_multiplier()))
