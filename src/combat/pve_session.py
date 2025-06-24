import random
import asyncio
from src.combat.session import CombatSession

# AI difficulty settings
AI_DIFFICULTIES = {
    "easy": {
        "name": "Easy",
        "stat_multiplier": 0.7,
        "smart_moves": False,
        "description": "Weaker stats"
    },
    "normal": {
        "name": "Normal", 
        "stat_multiplier": 1.0,
        "smart_moves": False,
        "description": "Normal stats"
    },
    "hard": {
        "name": "Hard",
        "stat_multiplier": 1.3,
        "smart_moves": True,
        "description": "Stronger stats, riskier rolls"
    }
}

class PVESession(CombatSession):
    """Extended combat session for PVE battles"""
    
    def __init__(self, player_id, player_card, ai_card, difficulty="normal"):
        # AI gets a special ID (negative to avoid conflicts)
        ai_id = -1
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
    
    def is_ai_turn(self):
        return self.turn == self.ai_id
    
    async def ai_take_turn(self):
        if not self.is_ai_turn() or self.is_finished():
            return None, None
        
        # AI always "rolls" after a short delay for realism
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        difficulty_settings = AI_DIFFICULTIES[self.difficulty]
        
        if difficulty_settings["smart_moves"]:
            # Hard AI tries to be strategic
            roll = self._smart_ai_roll()
        else:
            # Easy/Normal AI rolls randomly
            roll = random.randint(1, 6)
        
        damage, modifier = self.apply_roll(self.ai_id, roll)
        return roll, (damage, modifier)
    
    def _smart_ai_roll(self):
        # Get current HP percentages
        player_hp_pct = self.hp[self.player_id] / self.p1_card["hp"]
        ai_hp_pct = self.hp[self.ai_id] / self.p2_card["hp"]
        
        # If AI is low on health, try for higher rolls (risky but potentially rewarding)
        if ai_hp_pct < 0.3:
            return random.choices([1, 2, 3, 4, 5, 6], weights=[5, 10, 15, 20, 25, 25])[0]
        # If player is low on health, play more conservatively
        elif player_hp_pct < 0.3:
            return random.choices([1, 2, 3, 4, 5, 6], weights=[10, 15, 25, 25, 15, 10])[0]
        # Normal weighted roll favoring mid-range
        else:
            return random.choices([1, 2, 3, 4, 5, 6], weights=[5, 15, 25, 25, 20, 10])[0]