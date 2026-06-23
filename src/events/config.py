"""Declarative event registry.

Events rotate automatically on a deterministic schedule (see ``schedule.py``).
A daily event and a weekly event can be active at the same time; their effects
stack. Effect accessors live in ``service.py`` and are the only thing the rest of
the bot calls into.

To add an event: append an ``EventDef`` to ``DAILY_EVENTS`` or ``WEEKLY_EVENTS``.
The rotation cycles through each list in order, so the list length sets the cycle.
"""

from dataclasses import dataclass

# Drop-rate override used by "Double Drops". Kept here (rather than imported from
# src.shop.logic) to avoid an import cycle: shop.logic -> db -> events.service.
# Mirrors RARITY_POOL_BOOSTED in src/shop/logic.py.
DROP_POOL_BOOSTED = {
    "common": 50,
    "rare": 30,
    "epic": 15,
    "legendary": 5,
}


@dataclass(frozen=True)
class EventEffects:
    coin_mult: float = 1.0           # multiplies coins earned from rewards
    xp_mult: float = 1.0             # multiplies XP earned
    casino_payout_mult: float = 1.0  # multiplies casino payouts
    wager_cap_mult: float = 1.0      # multiplies the per-tier casino wager cap
    shop_discount: float = 0.0       # 0.0–1.0 fraction off shop prices
    drop_pool: dict | None = None    # rarity-weight override for card draws, else None
    casino_games: tuple = ()         # () = all games; else restrict casino effects to these


@dataclass(frozen=True)
class EventDef:
    id: str
    name: str
    description: str
    emoji: str
    cadence: str  # "daily" | "weekly"
    effects: EventEffects


# Cycled by day-index. Order defines the rotation.
DAILY_EVENTS: list[EventDef] = [
    EventDef(
        id="lucky_coins",
        name="Lucky Coins",
        description="Earn 50% more coins from rewards today.",
        emoji="🪙",
        cadence="daily",
        effects=EventEffects(coin_mult=1.5),
    ),
    EventDef(
        id="double_drops",
        name="Double Drops",
        description="Better odds for epic and legendary pulls today.",
        emoji="🎴",
        cadence="daily",
        effects=EventEffects(drop_pool=DROP_POOL_BOOSTED),
    ),
    EventDef(
        id="xp_surge",
        name="XP Surge",
        description="Gain 50% more XP from everything today.",
        emoji="⚡",
        cadence="daily",
        effects=EventEffects(xp_mult=1.5),
    ),
    EventDef(
        id="lucky_tables",
        name="Lucky Tables",
        description="Casino payouts are boosted 25% today.",
        emoji="🍀",
        cadence="daily",
        effects=EventEffects(casino_payout_mult=1.25),
    ),
]

# Cycled by week-index. Order defines the rotation.
WEEKLY_EVENTS: list[EventDef] = [
    EventDef(
        id="high_rollers",
        name="High Rollers Week",
        description="Double wager caps and +25% payouts at Blackjack & Roulette.",
        emoji="🎰",
        cadence="weekly",
        effects=EventEffects(
            wager_cap_mult=2.0,
            casino_payout_mult=1.25,
            casino_games=("blackjack", "roulette"),
        ),
    ),
    EventDef(
        id="shop_sale",
        name="Shop Sale Week",
        description="20% off all packs and cards in the shop.",
        emoji="🏷️",
        cadence="weekly",
        effects=EventEffects(shop_discount=0.20),
    ),
    EventDef(
        id="jackpot_week",
        name="Jackpot Week",
        description="All casino payouts boosted 50% this week.",
        emoji="💎",
        cadence="weekly",
        effects=EventEffects(casino_payout_mult=1.5),
    ),
]
