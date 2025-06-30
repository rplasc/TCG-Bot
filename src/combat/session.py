from datetime import datetime, timedelta, timezone

class CombatSession:
    def __init__(self, p1_id, p2_id, p1_card, p2_card):
        self.p1_id = p1_id
        self.p2_id = p2_id
        self.p1_card = p1_card.copy()
        self.p2_card = p2_card.copy()
        self.hp = {
            p1_id: p1_card["hp"],
            p2_id: p2_card["hp"]
        }
        self.turn = p1_id
        self.started_at = datetime.now(timezone.utc)
        self.last_action = datetime.now(timezone.utc)
        self.completed = False

    def get_opponent(self, user_id):
        return self.p2_id if user_id == self.p1_id else self.p1_id

    def is_player_turn(self, user_id):
        return self.turn == user_id

    def apply_roll(self, roller_id, roll):
        attacker = self.p1_card if roller_id == self.p1_id else self.p2_card
        defender = self.p2_card if roller_id == self.p1_id else self.p1_card
        target_id = self.get_opponent(roller_id)

        MODIFIERS = {1: 0, 2: 0.75, 3: 1.0, 4: 1.0, 5: 1.15, 6: 1.5}
        modifier = MODIFIERS[roll]
        damage = 0 if modifier == 0 else max(1, int(attacker["attack"] * modifier * (1 - min(0.75, defender["defense"] / 80))))
        self.hp[target_id] = max(0, self.hp[target_id] - damage)

        self.turn = target_id
        self.last_action = datetime.now(timezone.utc)

        return damage, modifier

    def has_timed_out(self):
        return datetime.now(timezone.utc) - self.last_action > timedelta(hours=1)

    def is_finished(self):
        return self.hp[self.p1_id] <= 0 or self.hp[self.p2_id] <= 0 or self.completed
