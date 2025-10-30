from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

DEFAULT_SESSION_TIMEOUT_HOURS = 1
MAX_DEFENSE_REDUCTION = 0.75
DEFENSE_CAP = 80

class CombatSession:
    
    # Damage modifiers based on dice roll
    ROLL_MODIFIERS: Dict[int, float] = {
        1: 0.0,    # Miss
        2: 0.75,   # Weak hit
        3: 1.0,    # Normal hit
        4: 1.0,    # Normal hit
        5: 1.15,   # Strong hit
        6: 1.5     # Critical hit
    }
    
    def __init__(self, p1_id: int, p2_id: int, p1_card: dict, p2_card: dict):

        self.p1_id = p1_id
        self.p2_id = p2_id

        self.p1_card = p1_card.copy()
        self.p2_card = p2_card.copy()
        self.hp = {
            p1_id: p1_card["hp"],
            p2_id: p2_card["hp"]
        }
        self.turn = p1_id  # Player 1 goes first
        self.started_at = datetime.now(timezone.utc)
        self.last_action = datetime.now(timezone.utc)
        self.completed = False

    def get_opponent(self, user_id: int) -> int:
        return self.p2_id if user_id == self.p1_id else self.p1_id

    def is_player_turn(self, user_id: int) -> bool:
        return self.turn == user_id

    def apply_roll(self, roller_id: int, roll: int) -> Tuple[int, float]:

        if roll not in self.ROLL_MODIFIERS:
            raise ValueError(f"Invalid roll: {roll}. Must be 1-6.")
        
        attacker = self.p1_card if roller_id == self.p1_id else self.p2_card
        defender = self.p2_card if roller_id == self.p1_id else self.p1_card
        target_id = self.get_opponent(roller_id)

        modifier = self.ROLL_MODIFIERS[roll]
        
        if modifier == 0:
            # Miss - no damage
            damage = 0
        else:
            # Calculate damage with defense reduction
            base_damage = attacker["attack"] * modifier
            defense_reduction = min(MAX_DEFENSE_REDUCTION, defender["defense"] / DEFENSE_CAP)
            damage = max(1, int(base_damage * (1 - defense_reduction)))
        
        # Apply damage
        self.hp[target_id] = max(0, self.hp[target_id] - damage)

        # Switch turn
        self.turn = target_id
        self.last_action = datetime.now(timezone.utc)

        return damage, modifier

    def has_timed_out(self, timeout_hours: int = DEFAULT_SESSION_TIMEOUT_HOURS) -> bool:
        return datetime.now(timezone.utc) - self.last_action > timedelta(hours=timeout_hours)

    def is_finished(self) -> bool:
        return self.hp[self.p1_id] <= 0 or self.hp[self.p2_id] <= 0 or self.completed
    
    def get_winner(self) -> int | None:

        if not self.is_finished():
            return None
        
        if self.hp[self.p1_id] <= 0:
            return self.p2_id
        elif self.hp[self.p2_id] <= 0:
            return self.p1_id
        
        return None
    
    def get_time_remaining(self, timeout_hours: int = DEFAULT_SESSION_TIMEOUT_HOURS) -> timedelta:
        elapsed = datetime.now(timezone.utc) - self.last_action
        timeout_duration = timedelta(hours=timeout_hours)
        remaining = timeout_duration - elapsed
        return max(timedelta(0), remaining)