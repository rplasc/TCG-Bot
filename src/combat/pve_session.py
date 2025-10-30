import random
import asyncio
from typing import Optional
from enum import Enum
from src.combat.session import CombatSession

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
    
    async def ai_take_turn(self) -> tuple[Optional[int], Optional[tuple[int, float]]]:
        if not self.is_ai_turn() or self.is_finished():
            return None, None
        
        try:
            # AI "thinks" for a realistic delay based on difficulty
            difficulty_settings = AI_DIFFICULTIES[self.difficulty]
            min_delay, max_delay = difficulty_settings["ai_delay"]
            await asyncio.sleep(random.uniform(min_delay, max_delay))
            
            if difficulty_settings["smart_moves"]:
                # Hard AI tries to be strategic
                roll = self._smart_ai_roll()
            else:
                # Easy/Normal AI rolls randomly
                roll = random.randint(1, 6)
            
            damage, modifier = self.apply_roll(self.ai_id, roll)
            return roll, (damage, modifier)
            
        except Exception as e:
            # Default to random roll if strategy fails
            roll = random.randint(1, 6)
            damage, modifier = self.apply_roll(self.ai_id, roll)
            return roll, (damage, modifier)
    
    def _smart_ai_roll(self) -> int:
        try:
            player_hp_pct = self.hp[self.player_id] / self.p1_card["hp"]
            ai_hp_pct = self.hp[self.ai_id] / self.p2_card["hp"]
            
            # If AI is low on health, try for higher rolls (risky but necessary)
            if ai_hp_pct < 0.3:
                weights = [5, 10, 15, 20, 25, 25]  # Favor 5 and 6
            # If player is low on health, play more conservatively (avoid 1 and 6)
            elif player_hp_pct < 0.3:
                weights = [10, 15, 25, 25, 15, 10]  # Favor middle rolls
            # Normal situation: slight preference for mid-high rolls
            else:
                weights = [5, 15, 25, 25, 20, 10]  # Balanced with slight high bias
            
            return random.choices([1, 2, 3, 4, 5, 6], weights=weights)[0]
        except Exception as e:
            return random.randint(1, 6)