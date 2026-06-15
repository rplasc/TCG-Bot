import random
import asyncio
from typing import Optional
from enum import Enum
from src.combat.session import (
    CombatSession,
    ACTION_STRIKE,
    ACTION_GUARD,
    ACTION_SPECIAL,
)

# Constants
PVE_SESSION_TIMEOUT_MINUTES = 30
AI_PLAYER_ID = -1

class Difficulty(Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"

# AI difficulty settings
AI_DIFFICULTIES = {
    "easy": {
        "name": "Easy",
        "stat_multiplier": 0.7,
        "smart_moves": False,
        "ai_delay": (0.5, 1.5),
        "description": "Weaker stats, slower reactions"
    },
    "normal": {
        "name": "Normal", 
        "stat_multiplier": 1.0,
        "smart_moves": False,
        "ai_delay": (1.0, 2.0),
        "description": "Normal stats, average speed"
    },
    "hard": {
        "name": "Hard",
        "stat_multiplier": 1.3,
        "smart_moves": True,
        "ai_delay": (1.5, 3.0),
        "description": "Stronger stats, strategic play"
    }
}

# Victory Rewards
PVE_COIN_REWARD = {
    "easy": 10,
    "normal": 15,
    "hard": 25
}

PVE_XP_REWARD = {
    "easy": 20,
    "normal": 35,
    "hard": 50
}

class PVESession(CombatSession):
    
    def __init__(self, player_id: int, player_card: dict, ai_card: dict, difficulty: str = "normal"):
        # AI gets a special ID (negative to avoid conflicts)
        ai_id = AI_PLAYER_ID
        super().__init__(player_id, ai_id, player_card, ai_card)
        
        self.difficulty = difficulty
        self.ai_id = ai_id
        self.player_id = player_id
        self.is_pve = True
        
        # Apply difficulty multipliers to AI card
        diff_settings = AI_DIFFICULTIES[difficulty]
        multiplier = diff_settings["stat_multiplier"]
        
        self.p2_card["attack"] = int(self.p2_card["attack"] * multiplier)
        self.p2_card["defense"] = int(self.p2_card["defense"] * multiplier)
        self.p2_card["hp"] = int(self.p2_card["hp"] * multiplier)
        self.hp[ai_id] = self.p2_card["hp"]
    
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

        # AI "thinks" for a realistic delay based on difficulty.
        difficulty_settings = AI_DIFFICULTIES[self.difficulty]
        min_delay, max_delay = difficulty_settings["ai_delay"]
        await asyncio.sleep(random.uniform(min_delay, max_delay))

        # Status tick (burn / stun / etc.) before acting.
        tick = self.start_turn(self.ai_id)
        if tick["skipped"] or self.is_finished():
            tick["action"] = "skip"
            return tick

        try:
            action = self._choose_ai_action(difficulty_settings["smart_moves"])
            return self.resolve_action(self.ai_id, action)
        except Exception:
            # Fall back to a plain strike if anything goes wrong.
            return self.resolve_action(self.ai_id, ACTION_STRIKE)

    def _choose_ai_action(self, smart: bool) -> str:
        ai_hp_pct = self.hp[self.ai_id] / max(1, self.p2_card["hp"])

        # Special whenever it's charged (strong play for every difficulty).
        if self.can_special(self.ai_id):
            return ACTION_SPECIAL

        if smart:
            # Hard AI: guard when hurt, otherwise press the attack.
            if ai_hp_pct < 0.35:
                return random.choices([ACTION_GUARD, ACTION_STRIKE], weights=[60, 40])[0]
            return ACTION_STRIKE

        # Easy / Normal: mostly strike, occasional guard when low.
        if ai_hp_pct < 0.3 and random.random() < 0.35:
            return ACTION_GUARD
        return ACTION_STRIKE