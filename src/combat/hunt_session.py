import random
import asyncio
from typing import Optional

from src.combat.session import (
    CombatSession,
    ACTION_STRIKE,
    ACTION_GUARD,
    ACTION_SPECIAL,
)

# Constants
HUNT_SESSION_TIMEOUT_MINUTES = 30
AI_PLAYER_ID = -1

# How much each enemy's stats grow per wave (compounding with the location base).
WAVE_GROWTH = 0.18


# Hunting grounds. Each location replaces the old abstract difficulties: it sets a
# base enemy stat multiplier, AI behavior, per-wave reward, themed monster names, and
# which outcome-event weight profile applies (see hunt_events.py).
LOCATIONS = {
    "woods": {
        "name": "Whispering Woods",
        "emoji": "🌲",
        "stat_multiplier": 0.75,
        "smart_moves": False,
        "ai_delay": (0.5, 1.5),
        "reward": {"coins": 6, "xp": 12},
        "monster_names": ["Thicket Stalker", "Mossback Boar", "Gloomwing Owl", "Bramble Lurker"],
        "description": "A gentle wood — good for new hunters.",
    },
    "tundra": {
        "name": "Frostpeak Tundra",
        "emoji": "🏔️",
        "stat_multiplier": 1.0,
        "smart_moves": False,
        "ai_delay": (1.0, 2.0),
        "reward": {"coins": 10, "xp": 20},
        "monster_names": ["Frostfang Wolf", "Rime Elk", "Glacier Yeti", "Snowveil Lynx"],
        "description": "Biting cold and hardy prey.",
    },
    "wastes": {
        "name": "Ember Wastes",
        "emoji": "🌋",
        "stat_multiplier": 1.3,
        "smart_moves": True,
        "ai_delay": (1.2, 2.5),
        "reward": {"coins": 16, "xp": 32},
        "monster_names": ["Cinder Drake", "Magma Crawler", "Ashen Revenant", "Scorch Hound"],
        "description": "Scorched lands where cunning beasts roam.",
    },
    "depths": {
        "name": "Forgotten Depths",
        "emoji": "🌑",
        "stat_multiplier": 1.6,
        "smart_moves": True,
        "ai_delay": (1.5, 3.0),
        "reward": {"coins": 24, "xp": 48},
        "monster_names": ["Void Leech", "Abyssal Horror", "Dread Sentinel", "Shadow Maw"],
        "description": "Only the boldest return from the dark.",
    },
}

DEFAULT_LOCATION = "tundra"


def get_location(location: str) -> dict:
    return LOCATIONS.get(location, LOCATIONS[DEFAULT_LOCATION])


class HuntSession(CombatSession):
    """A multi-wave hunt against successive enemies at one location.

    Player HP/energy/statuses carry over between waves; enemy state is reset for each
    fresh foe. Rewards accumulate into a pot that is only granted when the player banks
    and leaves — dying forfeits the pot.
    """

    def __init__(self, player_id: int, player_card: dict, ai_card: dict, location: str = DEFAULT_LOCATION):
        ai_id = AI_PLAYER_ID
        super().__init__(player_id, ai_id, player_card, ai_card)

        self.location = location if location in LOCATIONS else DEFAULT_LOCATION
        self.ai_id = ai_id
        self.player_id = player_id
        self.is_pve = True

        # Expedition state.
        self.wave = 1
        self.pending_coins = 0
        self.pending_xp = 0
        self.waves_cleared = 0
        self._elite_next = False    # set by outcome events (Apex Beast)
        self._weaken_next = False   # set by outcome events (Prey Flees)

        self._spawn_enemy(ai_card, elite=False)

    # --- Difficulty / scaling -------------------------------------------

    def _wave_multiplier(self) -> float:
        base = get_location(self.location)["stat_multiplier"]
        return base * (1 + WAVE_GROWTH * (self.wave - 1))

    def _spawn_enemy(self, ai_card: dict, elite: bool = False):
        """Scale and theme a fresh enemy card, then reset enemy-side combat state."""
        mult = self._wave_multiplier()
        if elite:
            mult *= 1.4
        if self._weaken_next:
            mult *= 0.7
            self._weaken_next = False

        self.p2_card = ai_card.copy()
        self.p2_card["attack"] = max(1, int(self.p2_card["attack"] * mult))
        self.p2_card["defense"] = max(0, int(self.p2_card["defense"] * mult))
        self.p2_card["hp"] = max(1, int(self.p2_card["hp"] * mult))

        # Themed name (keeps the underlying card's rarity for archetype/crit logic).
        names = get_location(self.location)["monster_names"]
        name = random.choice(names)
        self.p2_card["name"] = f"⭐ Elite {name}" if elite else name

        # Reset enemy-side state for the new foe; player state carries over.
        self.hp[self.ai_id] = self.p2_card["hp"]
        self.energy[self.ai_id] = 0
        self.shield[self.ai_id] = 0
        self.statuses[self.ai_id] = []
        self.momentum[self.ai_id] = 0
        self.turn = self.player_id
        self.completed = False

    def next_wave(self, ai_card: dict):
        """Advance to the next wave with a fresh (tougher) enemy."""
        self.wave += 1
        elite = self._elite_next
        self._elite_next = False
        self._spawn_enemy(ai_card, elite=elite)
        self.log.append(f"⚔️ Wave {self.wave}: **{self.p2_card['name']}** appears!")

    def queue_elite(self):
        self._elite_next = True

    def queue_weaken(self):
        self._weaken_next = True

    # --- Rewards --------------------------------------------------------

    def wave_reward(self) -> dict:
        """Accumulate this wave's reward into the pot and return the amounts gained."""
        base = get_location(self.location)["reward"]
        depth = 1 + 0.5 * (self.wave - 1)
        elite_bonus = 1.5 if self.p2_card.get("name", "").startswith("⭐") else 1.0
        coins = int(base["coins"] * depth * elite_bonus)
        xp = int(base["xp"] * depth * elite_bonus)
        self.pending_coins += coins
        self.pending_xp += xp
        self.waves_cleared += 1
        return {"coins": coins, "xp": xp}

    # --- AI turn (unchanged behavior, sourced from location) ------------

    def is_ai_turn(self) -> bool:
        return self.turn == self.ai_id

    async def ai_take_turn(self) -> Optional[dict]:
        """Run the AI's turn: tick statuses, choose an action, resolve it.

        Returns the structured result dict from ``resolve_action`` (with the chosen
        action), or ``None`` if it isn't the AI's turn / the battle is over / the
        turn was skipped by a stun.
        """
        if not self.is_ai_turn() or self.is_finished():
            return None

        loc = get_location(self.location)
        min_delay, max_delay = loc["ai_delay"]
        await asyncio.sleep(random.uniform(min_delay, max_delay))

        # Status tick (burn / stun / etc.) before acting.
        tick = self.start_turn(self.ai_id)
        if tick["skipped"] or self.is_finished():
            tick["action"] = "skip"
            return tick

        try:
            action = self._choose_ai_action(loc["smart_moves"])
            return self.resolve_action(self.ai_id, action)
        except Exception:
            return self.resolve_action(self.ai_id, ACTION_STRIKE)

    def _choose_ai_action(self, smart: bool) -> str:
        ai_hp_pct = self.hp[self.ai_id] / max(1, self.p2_card["hp"])

        if self.can_special(self.ai_id):
            return ACTION_SPECIAL

        if smart:
            if ai_hp_pct < 0.35:
                return random.choices([ACTION_GUARD, ACTION_STRIKE], weights=[60, 40])[0]
            return ACTION_STRIKE

        if ai_hp_pct < 0.3 and random.random() < 0.35:
            return ACTION_GUARD
        return ACTION_STRIKE
