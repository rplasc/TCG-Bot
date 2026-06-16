"""Centralized economy configuration.

Tiers, casino wager caps, repeatable-reward budgets, and stable ledger source
names. Reward constants can migrate here gradually; this first pass only defines
what the casino-safety + telemetry work needs.
"""

STARTING_COINS = 35

# Player tiers shaped by level. max_level of None means "and above".
LEVEL_TIERS = [
    {"name": "new", "min_level": 0, "max_level": 4},
    {"name": "early", "min_level": 5, "max_level": 9},
    {"name": "mid", "min_level": 10, "max_level": 19},
    {"name": "veteran", "min_level": 20, "max_level": None},
]

# Casino max wager by tier (applies across Blackjack, Slots, Roulette).
CASINO_WAGER_CAPS = {
    "new": 50,
    "early": 150,
    "mid": 500,
    "veteran": 1000,
}

# Daily full-value repeatable coin budget by tier. Defined for forward use;
# not consumed yet (soft caps are a later phase).
DAILY_REPEATABLE_COIN_BUDGETS = {
    "new": 100,
    "early": 200,
    "mid": 350,
    "veteran": 500,
}

# Stable ledger source names (see currency-redesign-technical-plan.md).
DAILY_CLAIM = "daily.claim"
DAILY_STREAK_BONUS = "daily.streak_bonus"
SHOP_PACK_PURCHASE = "shop.pack_purchase"
SHOP_CARD_PURCHASE = "shop.card_purchase"
SHOP_DUPLICATE_REFUND = "shop.duplicate_refund"
COLLECTION_CARD_SALE = "collection.card_sale"
COLLECTION_REWARD = "collection.reward"
COMBAT_PVP_WIN = "combat.pvp_win"
COMBAT_HUNT_BANK = "combat.hunt_bank"
LEVEL_UP_REWARD = "level.up_reward"
CASINO_WAGER = "casino.wager"
CASINO_PAYOUT = "casino.payout"
TRADE_OFFER_TRANSFER = "trade.offer_transfer"
TRADE_FEE = "trade.fee"
ADMIN_ADJUSTMENT = "admin.adjustment"
EVENT_REWARD = "event.reward"
CHALLENGE_REWARD = "challenge.reward"


# --- Daily repeatable reward budget (soft caps) ---

# Budget categories for the daily_reward_budgets table.
BUDGET_REPEATABLE = "repeatable"
BUDGET_CASINO_NET = "casino_net"
BUDGET_COMBAT = "combat"
BUDGET_HUNT = "hunt"
BUDGET_CHALLENGE = "challenge"
BUDGET_EVENT = "event"

# Categories that count toward the shared repeatable cap AND get reduced once
# the tier budget is exceeded. casino_net is tracked separately for telemetry
# only and is intentionally excluded here.
REDUCIBLE_BUDGET_CATEGORIES = (BUDGET_HUNT, BUDGET_COMBAT, BUDGET_REPEATABLE)

# Diminishing-returns bands, expressed as (cumulative-multiple-of-budget upper
# bound, payout multiplier). The last band uses None as an open upper bound.
#   0%–100% of budget  -> full value
#   100%–150%          -> 50%
#   150%+              -> 25%
REPEATABLE_SOFT_CAP_BANDS = [
    (1.0, 1.0),
    (1.5, 0.5),
    (None, 0.25),
]


# --- Trade fee (coin sink on player-to-player coin transfers) ---

# Fee charged to the trade initiator as a fraction of the coins they offer.
TRADE_FEE_PERCENT = 0.05


def trade_fee_for(coins_offered: int) -> int:
    """Coin fee for a trade offering `coins_offered` coins (floored, 0 if none)."""
    if coins_offered <= 0:
        return 0
    return int(coins_offered * TRADE_FEE_PERCENT)


def tier_for_level(level: int) -> str:
    """Return the tier name for a player level."""
    for tier in LEVEL_TIERS:
        max_level = tier["max_level"]
        if level >= tier["min_level"] and (max_level is None or level <= max_level):
            return tier["name"]
    return LEVEL_TIERS[0]["name"]
