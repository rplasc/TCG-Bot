"""Outcome events for hunts — the "unexpected" layer.

After a wave is won, one of these may fire before the player chooses to press deeper or
bank. Each event only mutates in-memory ``HuntSession`` state (no DB, no discord), so it
needs no schema changes. Events are picked with weights that vary by location: calmer
grounds favor helpful or no-op outcomes, dangerous grounds lean toward risk and reward.
"""

import random

from src.combat import mechanics


def _treasure_haul(session) -> str:
    base = max(5, session.pending_coins)
    bonus = random.randint(int(base * 0.25) + 5, int(base * 0.5) + 12)
    session.pending_coins += bonus
    return f"You unearth a hidden cache — **+{bonus}** coins added to your haul!"


def _hidden_spring(session) -> str:
    max_hp = session.p1_card["hp"]
    heal = max(1, int(max_hp * random.uniform(0.2, 0.35)))
    before = session.hp[session.player_id]
    session.hp[session.player_id] = min(max_hp, before + heal)
    gained = session.hp[session.player_id] - before
    return f"You rest at a hidden spring and recover **{gained}** HP."


def _found_supplies(session) -> str:
    amount = random.randint(25, 45)
    session.energy[session.player_id] = min(
        mechanics.MAX_ENERGY, session.energy[session.player_id] + amount
    )
    return f"You scavenge supplies — **+{amount}** energy for the next fight."


def _prey_flees(session) -> str:
    # A little extra loot, and the next enemy spawns rattled (weakened on arrival).
    bonus = random.randint(4, 10)
    session.pending_coins += bonus
    session.queue_weaken()
    return f"Startled prey scatters, dropping **+{bonus}** coins. The next beast seems wary..."


def _apex_beast(session) -> str:
    session.queue_elite()
    return "A massive shadow stirs — an **Elite** beast now stalks your next wave. Greater danger, greater reward."


def _lingering_wound(session) -> str:
    # Player carries a debuff into the next wave (resolved here, at the outcome).
    if random.random() < 0.5:
        session.statuses[session.player_id].append(mechanics.make_status("weaken", turns=2, magnitude=0.2))
        return "You're nursing a wound — your attacks are **weakened** going into the next fight."
    burn = max(1, int(session.p1_card["attack"] * 0.08))
    session.statuses[session.player_id].append(mechanics.make_status("burn", turns=2, magnitude=burn))
    return "A venomous nick festers — you're **bleeding** into the next fight."


def _quiet(session) -> str:
    return random.choice([
        "The wilds fall quiet. You press on, undisturbed.",
        "Nothing stirs. You catch your breath.",
        "A calm moment between the hunt.",
    ])


# Each event: title/emoji for display + the effect function.
EVENTS = {
    "treasure":  {"title": "Treasure Haul",      "emoji": "💰", "apply": _treasure_haul},
    "spring":    {"title": "Hidden Spring",      "emoji": "💧", "apply": _hidden_spring},
    "supplies":  {"title": "Found Supplies",     "emoji": "🎒", "apply": _found_supplies},
    "flees":     {"title": "Prey Flees",         "emoji": "🐾", "apply": _prey_flees},
    "apex":      {"title": "Apex Beast Stalks You", "emoji": "👁️", "apply": _apex_beast},
    "wound":     {"title": "Lingering Wound",    "emoji": "🩸", "apply": _lingering_wound},
    "quiet":     {"title": "All Quiet",          "emoji": "🍃", "apply": _quiet},
}

# Per-location weighting. Keys map to LOCATIONS in hunt_session.py.
_LOCATION_WEIGHTS = {
    "woods":  {"quiet": 30, "treasure": 18, "spring": 20, "supplies": 14, "flees": 12, "apex": 3,  "wound": 3},
    "tundra": {"quiet": 25, "treasure": 20, "spring": 16, "supplies": 14, "flees": 10, "apex": 7,  "wound": 8},
    "wastes": {"quiet": 18, "treasure": 24, "spring": 12, "supplies": 12, "flees": 8,  "apex": 14, "wound": 12},
    "depths": {"quiet": 12, "treasure": 28, "spring": 10, "supplies": 10, "flees": 6,  "apex": 20, "wound": 14},
}

_DEFAULT_WEIGHTS = _LOCATION_WEIGHTS["tundra"]


def roll_outcome_event(session) -> dict:
    """Pick a weighted outcome event for the session's location, apply it, and return
    display info: {"title", "emoji", "desc"}.
    """
    weights = _LOCATION_WEIGHTS.get(getattr(session, "location", None), _DEFAULT_WEIGHTS)
    keys = list(weights.keys())
    chosen = random.choices(keys, weights=[weights[k] for k in keys])[0]
    event = EVENTS[chosen]
    desc = event["apply"](session)
    return {"title": event["title"], "emoji": event["emoji"], "desc": desc}
