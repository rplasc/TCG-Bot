"""Pari-mutuel sports-betting logic.

One auto-generated matchup runs per "match day" (8 AM PST rollover). Players bet
coins on side A or B; the displayed decimal odds are pool ratios (seeded with a
small random phantom amount) that drift live as real bets arrive. At end of day a
winner is drawn weighted by each team's hidden strength, and the pool — minus a
house rake — is split among the winning side proportional to stake. If the winning
side has no real bettors (or there were no bets at all), every stake is refunded.
"""

import random

from src.database.db import (
    create_sports_match,
    get_match_by_day,
    get_open_matches_before,
    get_match_pools,
    get_user_bet_side,
    insert_sports_bet,
    get_bets_for_match,
    mark_match_settled,
    update_casino_stats,
)
from src.economy.service import award_coins
from src.economy.config import SPORTS_PAYOUT, SPORTS_REFUND, SPORTS_RAKE_PERCENT
from src.utils.time import get_sports_rotation_key

_ADJECTIVES = [
    "Crimson", "Azure", "Golden", "Shadow", "Iron", "Frost", "Ember", "Storm",
    "Savage", "Royal", "Phantom", "Thunder", "Silent", "Rapid", "Mighty", "Wild",
]
_NOUNS = [
    "Wolves", "Sharks", "Hawks", "Bears", "Dragons", "Titans", "Vipers", "Falcons",
    "Ravens", "Lions", "Cobras", "Stallions", "Panthers", "Griffins", "Bulls", "Foxes",
]

SEED_MIN = 50
SEED_MAX = 200


def _random_team_pair() -> tuple[str, str]:
    nouns = random.sample(_NOUNS, 2)
    adjs = random.sample(_ADJECTIVES, 2)
    return f"{adjs[0]} {nouns[0]}", f"{adjs[1]} {nouns[1]}"


async def get_or_create_today_match() -> dict:
    """Return today's match, creating it (with random teams, strengths and odds
    seeds) if it doesn't exist yet. Restart-safe via UNIQUE(match_day)."""
    day = get_sports_rotation_key()
    existing = await get_match_by_day(day)
    if existing:
        return existing

    team_a, team_b = _random_team_pair()
    # Hidden strengths bias the winner draw so the displayed odds are meaningful.
    strength_a = round(random.uniform(0.8, 1.6), 3)
    strength_b = round(random.uniform(0.8, 1.6), 3)
    seed_a = random.randint(SEED_MIN, SEED_MAX)
    seed_b = random.randint(SEED_MIN, SEED_MAX)
    await create_sports_match(day, team_a, team_b, strength_a, strength_b, seed_a, seed_b)
    return await get_match_by_day(day)


async def compute_odds(match: dict) -> dict:
    """Decimal pari-mutuel odds per side: (total + seeds) / (side + side_seed).
    Returns {'a': float, 'b': float} along with the live real pools."""
    pools = await get_match_pools(match["id"])
    eff_a = pools["a"] + match["seed_a"]
    eff_b = pools["b"] + match["seed_b"]
    total = eff_a + eff_b
    return {
        "a": round(total / eff_a, 2) if eff_a else 1.0,
        "b": round(total / eff_b, 2) if eff_b else 1.0,
        "pool_a": pools["a"],
        "pool_b": pools["b"],
    }


async def check_bet_allowed(user_id: int, match: dict, side: str) -> tuple[bool, str]:
    """Enforce the single-side rule. Call before charging coins; the actual bet row
    is written with ``record_bet`` only after a successful charge."""
    existing = await get_user_bet_side(match["id"], user_id)
    if existing is not None and existing != side:
        other = match["team_b"] if existing == "a" else match["team_a"]
        return False, f"❌ You already backed **{other}** in this match — you can't bet both sides."
    return True, "ok"


async def record_bet(user_id: int, match: dict, side: str, amount: int) -> None:
    """Persist a bet row (caller must have already charged the player)."""
    await insert_sports_bet(match["id"], user_id, side, amount)


def _draw_winner(match: dict) -> str:
    total = match["strength_a"] + match["strength_b"]
    return "a" if random.uniform(0, total) < match["strength_a"] else "b"


async def settle_match(match: dict) -> dict:
    """Resolve a match: draw the winner, pay the winning side from the pool (minus
    rake), or refund everyone if there are no winners. Marks the match settled and
    returns a summary for announcing."""
    bets = await get_bets_for_match(match["id"])
    pools = await get_match_pools(match["id"])
    total_pool = pools["a"] + pools["b"]

    winner = _draw_winner(match)
    winning_team = match["team_a"] if winner == "a" else match["team_b"]
    winning_total = pools[winner]

    # Total each user staked across the match (for telemetry).
    wagered: dict[int, int] = {}
    for user_id, _side, amount in bets:
        wagered[user_id] = wagered.get(user_id, 0) + amount

    payouts: dict[int, int] = {}
    refunded = False

    if total_pool == 0:
        # Nobody played; nothing to settle beyond recording the result.
        await mark_match_settled(match["id"], winner)
        return {
            "match": match, "winner": winner, "winning_team": winning_team,
            "total_pool": 0, "distributable": 0, "rake": 0,
            "winners": 0, "refunded": False,
        }

    if winning_total == 0:
        # No one backed the winning side: refund all stakes in full (no rake).
        refunded = True
        winner = "void"
        for user_id, amount in wagered.items():
            await award_coins(user_id, amount, SPORTS_REFUND,
                              {"match_id": match["id"], "reason": "no_winners"})
            payouts[user_id] = amount
        distributable = total_pool
        rake = 0
    else:
        distributable = int(total_pool * (1 - SPORTS_RAKE_PERCENT))
        rake = total_pool - distributable
        # Proportional split among winning-side stakes.
        for user_id, side, amount in bets:
            if side != winner:
                continue
            share = int(distributable * amount / winning_total)
            payouts[user_id] = payouts.get(user_id, 0) + share
        for user_id, amount in payouts.items():
            await award_coins(user_id, amount, SPORTS_PAYOUT,
                              {"match_id": match["id"], "winner": winner})

    # One telemetry row per participant: their total stake and total return.
    for user_id, wager in wagered.items():
        await update_casino_stats(user_id, wager=wager, payout=payouts.get(user_id, 0))

    await mark_match_settled(match["id"], winner)
    return {
        "match": match, "winner": winner, "winning_team": winning_team,
        "total_pool": total_pool, "distributable": distributable, "rake": rake,
        "winners": len(payouts), "refunded": refunded,
    }


async def settle_due_matches() -> list[dict]:
    """Settle every open match whose day has passed. Returns settlement summaries."""
    day = get_sports_rotation_key()
    due = await get_open_matches_before(day)
    return [await settle_match(m) for m in due]
