"""Pure combat mechanics: derived card profiles, actions, status effects, and
rendering helpers. No database or discord imports live here so PVP, PVE, and the AI
can all share the same rules.

All new combat state (energy, statuses, momentum, log) is tracked in-memory on the
session — nothing here requires database schema changes. Cards only need the existing
``rarity``, ``attack``, ``defense`` and ``hp`` fields.
"""

import random

# --- Tuning constants -------------------------------------------------------

MAX_DEFENSE_REDUCTION = 0.75
DEFENSE_CAP = 80
MAX_ENERGY = 100

# Damage modifiers based on dice roll (kept identical to the original system).
ROLL_MODIFIERS = {
    1: 0.0,    # Miss
    2: 0.75,   # Weak hit
    3: 1.0,    # Normal hit
    4: 1.0,    # Normal hit
    5: 1.15,   # Strong hit
    6: 1.5,    # Critical hit
}

# Energy generated per action.
STRIKE_ENERGY = 25
GUARD_ENERGY = 35
SPECIAL_COST = MAX_ENERGY

# Guard halves the next incoming hit.
GUARD_DAMAGE_MULTIPLIER = 0.5


# --- Rarity power tiers ------------------------------------------------------

# Each rarity grants a crit chance, crit damage multiplier, an energy bonus per
# action, and a potency multiplier that scales Special-ability effects.
RARITY_TIERS = {
    "common":    {"crit_chance": 0.05, "crit_mult": 1.5, "energy_bonus": 0,  "potency": 1.0},
    "rare":      {"crit_chance": 0.10, "crit_mult": 1.6, "energy_bonus": 5,  "potency": 1.15},
    "epic":      {"crit_chance": 0.18, "crit_mult": 1.8, "energy_bonus": 10, "potency": 1.3},
    "legendary": {"crit_chance": 0.28, "crit_mult": 2.0, "energy_bonus": 15, "potency": 1.5},
}

DEFAULT_TIER = "common"


def get_tier(card: dict) -> dict:
    """Return the rarity tier settings for a card, defaulting to common."""
    rarity = str(card.get("rarity", "") or "").strip().lower()
    return RARITY_TIERS.get(rarity, RARITY_TIERS[DEFAULT_TIER])


# --- Archetypes (derived from stat balance) ---------------------------------

AGGRESSOR = "Aggressor"
GUARDIAN = "Guardian"
JUGGERNAUT = "Juggernaut"
BALANCED = "Balanced"

ARCHETYPE_ICONS = {
    AGGRESSOR: "🔥",
    GUARDIAN: "🛡️",
    JUGGERNAUT: "💪",
    BALANCED: "⚖️",
}


def get_archetype(card: dict) -> str:
    """Classify a card's fighting style by which stat dominates.

    Compares each stat against the average of all three. The most-dominant stat
    decides the archetype; if nothing stands out clearly the card is Balanced.
    """
    atk = max(1, int(card.get("attack", 1)))
    dfn = max(1, int(card.get("defense", 1)))
    hp = max(1, int(card.get("hp", 1)))

    # Normalize HP to a comparable scale (HP pools are far larger than ATK/DEF).
    hp_scaled = hp / 4.0

    stats = {AGGRESSOR: atk, GUARDIAN: dfn, JUGGERNAUT: hp_scaled}
    avg = sum(stats.values()) / 3.0

    leader = max(stats, key=stats.get)
    # Require the leader to be at least 20% above the average to count as dominant.
    if avg > 0 and stats[leader] >= avg * 1.20:
        return leader
    return BALANCED


# --- Special abilities (one per archetype) ----------------------------------

# Each Special spends full energy. ``base`` numbers are scaled by the caster's
# rarity potency at resolution time.
SPECIALS = {
    AGGRESSOR: {
        "name": "Inferno Rush",
        "emoji": "🔥",
        "desc": "A blazing assault that burns the foe over time.",
        "damage_mult": 1.8,   # of attack
        "burn": {"magnitude": 0.10, "turns": 3},  # 10% of attacker ATK / turn
    },
    GUARDIAN: {
        "name": "Aegis Bulwark",
        "emoji": "🛡️",
        "desc": "Raise a shield and mend wounds.",
        "damage_mult": 0.6,
        "shield": 0.9,        # shield = 90% of own attack
        "heal": 0.4,          # heal = 40% of own attack
    },
    JUGGERNAUT: {
        "name": "Seismic Slam",
        "emoji": "💥",
        "desc": "A crushing blow that stuns the enemy.",
        "damage_mult": 1.4,
        "stun": 1,            # enemy skips 1 turn
    },
    BALANCED: {
        "name": "Perfect Strike",
        "emoji": "🌟",
        "desc": "A guaranteed critical blow that refunds energy.",
        "damage_mult": 1.5,
        "guaranteed_crit": True,
        "energy_refund": 40,
        "weaken": {"magnitude": 0.25, "turns": 2},  # cut enemy ATK 25%
    },
}


def get_special(card: dict) -> dict:
    return SPECIALS[get_archetype(card)]


# --- Damage & crit -----------------------------------------------------------

def damage_after_defense(base_damage: float, defender_defense: int) -> int:
    """Apply the defense reduction formula. Minimum 1 damage when base > 0."""
    if base_damage <= 0:
        return 0
    reduction = min(MAX_DEFENSE_REDUCTION, defender_defense / DEFENSE_CAP)
    return max(1, int(base_damage * (1 - reduction)))


def roll_is_crit(card: dict, roll: int) -> bool:
    """A natural 6 always crits; otherwise rarity crit chance applies on hits."""
    if roll == 6:
        return True
    if ROLL_MODIFIERS.get(roll, 0) <= 0:
        return False
    return random.random() < get_tier(card)["crit_chance"]


# --- Status effects ----------------------------------------------------------
#
# A status is a dict: {"type", "turns", "magnitude"}. They live in a list per
# player on the session and tick at the start of that player's turn.

def make_status(stype: str, turns: int, magnitude: float = 0) -> dict:
    return {"type": stype, "turns": int(turns), "magnitude": magnitude}


STATUS_ICONS = {
    "burn": "🔥",
    "stun": "💫",
    "weaken": "⬇️",
    "shield": "🛡️",
    "guard": "✋",
}


def status_icons(statuses: list, shield: int = 0) -> str:
    """Compact icon string summarizing a fighter's active statuses."""
    parts = []
    if shield > 0:
        parts.append(f"🛡️{shield}")
    for s in statuses:
        icon = STATUS_ICONS.get(s["type"], "•")
        if s["type"] in ("burn", "stun", "weaken"):
            parts.append(f"{icon}{s['turns']}")
        elif s["type"] == "guard":
            parts.append(icon)
    return " ".join(parts)


# --- Rendering helpers -------------------------------------------------------

def _hp_heart(pct: float) -> str:
    if pct > 0.6:
        return "💚"
    if pct > 0.3:
        return "💛"
    return "❤️"


def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """HP bar whose heart shifts color (green/yellow/red) with remaining HP."""
    current = max(0, current)
    pct = (current / maximum) if maximum > 0 else 0
    filled = max(0, min(length, int(pct * length)))
    heart = _hp_heart(pct)
    return f"{heart} [{'█' * filled}{'░' * (length - filled)}] {current}/{maximum}"


def energy_bar(current: int, length: int = 10) -> str:
    """Energy meter; shows a charged marker when the Special is ready."""
    current = max(0, min(MAX_ENERGY, current))
    filled = int((current / MAX_ENERGY) * length)
    filled = max(0, min(length, filled))
    ready = "⚡READY" if current >= SPECIAL_COST else ""
    return f"🔋 [{'▰' * filled}{'▱' * (length - filled)}] {current}/{MAX_ENERGY} {ready}".rstrip()


# --- Flavor text -------------------------------------------------------------

_CRIT_LINES = [
    "A devastating critical hit!",
    "Bullseye — critical damage!",
    "That one's going to leave a mark!",
]
_MISS_LINES = [
    "Whiffed completely!",
    "A clumsy miss!",
    "The attack sails wide!",
]
_LOW_HP_LINES = [
    "is on the ropes!",
    "is barely standing!",
    "is hanging by a thread!",
]
_COMEBACK_LINES = [
    "momentum is shifting!",
    "is mounting a comeback!",
    "refuses to go down!",
]


def flavor_text(event: str, name: str = "") -> str:
    """Short reactive line for a combat event."""
    if event == "crit":
        return f"💥 {random.choice(_CRIT_LINES)}"
    if event == "miss":
        return f"💨 {random.choice(_MISS_LINES)}"
    if event == "low_hp":
        return f"🩸 **{name}** {random.choice(_LOW_HP_LINES)}"
    if event == "comeback":
        return f"🔆 **{name}** {random.choice(_COMEBACK_LINES)}"
    return ""
