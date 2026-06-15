import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from src.combat import mechanics

DEFAULT_SESSION_TIMEOUT_HOURS = 1
MAX_DEFENSE_REDUCTION = mechanics.MAX_DEFENSE_REDUCTION
DEFENSE_CAP = mechanics.DEFENSE_CAP

MAX_LOG_LINES = 4

# Valid player actions.
ACTION_STRIKE = "strike"
ACTION_GUARD = "guard"
ACTION_SPECIAL = "special"


class CombatSession:

    # Damage modifiers based on dice roll (sourced from mechanics for sharing).
    ROLL_MODIFIERS: Dict[int, float] = mechanics.ROLL_MODIFIERS

    def __init__(self, p1_id: int, p2_id: int, p1_card: dict, p2_card: dict):

        self.p1_id = p1_id
        self.p2_id = p2_id

        self.p1_card = p1_card.copy()
        self.p2_card = p2_card.copy()
        self.hp = {
            p1_id: p1_card["hp"],
            p2_id: p2_card["hp"]
        }

        # --- New dynamic combat state (all in-memory, no schema change) ---
        self.energy: Dict[int, int] = {p1_id: 0, p2_id: 0}
        self.shield: Dict[int, int] = {p1_id: 0, p2_id: 0}
        self.statuses: Dict[int, List[dict]] = {p1_id: [], p2_id: []}
        self.momentum: Dict[int, int] = {p1_id: 0, p2_id: 0}  # consecutive hits
        self.log: List[str] = []

        self.turn = p1_id  # Player 1 goes first
        self.started_at = datetime.now(timezone.utc)
        self.last_action = datetime.now(timezone.utc)
        self.completed = False

    # --- Helpers --------------------------------------------------------

    def get_opponent(self, user_id: int) -> int:
        return self.p2_id if user_id == self.p1_id else self.p1_id

    def get_card(self, user_id: int) -> dict:
        return self.p1_card if user_id == self.p1_id else self.p2_card

    def is_player_turn(self, user_id: int) -> bool:
        return self.turn == user_id

    def name_of(self, user_id: int) -> str:
        return self.get_card(user_id)["name"]

    def can_special(self, user_id: int) -> bool:
        return self.energy[user_id] >= mechanics.SPECIAL_COST

    def _add_log(self, line: str):
        if not line:
            return
        self.log.append(line)
        if len(self.log) > MAX_LOG_LINES:
            self.log = self.log[-MAX_LOG_LINES:]

    def _gain_energy(self, user_id: int, amount: int):
        bonus = mechanics.get_tier(self.get_card(user_id))["energy_bonus"]
        self.energy[user_id] = min(mechanics.MAX_ENERGY, self.energy[user_id] + amount + bonus)

    def _has_status(self, user_id: int, stype: str) -> bool:
        return any(s["type"] == stype for s in self.statuses[user_id])

    def _effective_attack(self, user_id: int) -> int:
        """Attack after weaken statuses are applied."""
        atk = self.get_card(user_id)["attack"]
        for s in self.statuses[user_id]:
            if s["type"] == "weaken":
                atk = int(atk * (1 - s["magnitude"]))
        return max(1, atk)

    def _deal_damage(self, target_id: int, amount: int) -> int:
        """Apply damage to a target, absorbing with shield first. Returns HP lost."""
        if amount <= 0:
            return 0
        if self.shield[target_id] > 0:
            absorbed = min(self.shield[target_id], amount)
            self.shield[target_id] -= absorbed
            amount -= absorbed
        self.hp[target_id] = max(0, self.hp[target_id] - amount)
        return amount

    # --- Turn lifecycle -------------------------------------------------

    def start_turn(self, user_id: int) -> dict:
        """Tick statuses at the start of ``user_id``'s turn.

        Returns a dict: {"skipped": bool, "lines": [str], "burn": int}.
        Burn deals damage-over-time; stun causes the turn to be skipped; guard and
        timed statuses count down.
        """
        lines: List[str] = []
        burn_total = 0
        skipped = False

        remaining: List[dict] = []
        for s in self.statuses[user_id]:
            if s["type"] == "burn":
                dmg = max(1, int(s["magnitude"]))
                self._deal_damage(user_id, dmg)
                burn_total += dmg
            elif s["type"] == "stun":
                skipped = True

            s["turns"] -= 1
            if s["turns"] > 0:
                remaining.append(s)
        self.statuses[user_id] = remaining

        if burn_total:
            line = f"🔥 **{self.name_of(user_id)}** takes {burn_total} burn damage!"
            lines.append(line)
            self._add_log(line)
        if skipped:
            line = f"💫 **{self.name_of(user_id)}** is stunned and skips a turn!"
            lines.append(line)
            self._add_log(line)
            # Stun consumes the turn; pass to opponent.
            self.turn = self.get_opponent(user_id)
            self.last_action = datetime.now(timezone.utc)

        return {"skipped": skipped, "lines": lines, "burn": burn_total}

    # --- Action resolution ----------------------------------------------

    def resolve_action(self, actor_id: int, action: str) -> dict:
        """Resolve a player action and return a structured result.

        Result keys: action, roll, damage, crit, missed, lines (list of log lines),
        special_name (optional). Updates HP, energy, statuses, momentum, log, and
        switches the turn.
        """
        target_id = self.get_opponent(actor_id)
        result = {
            "action": action,
            "roll": None,
            "damage": 0,
            "crit": False,
            "missed": False,
            "lines": [],
            "special_name": None,
        }

        if action == ACTION_GUARD:
            self._resolve_guard(actor_id, result)
        elif action == ACTION_SPECIAL and self.can_special(actor_id):
            self._resolve_special(actor_id, target_id, result)
        else:
            # Default / fallback is a Strike.
            result["action"] = ACTION_STRIKE
            self._resolve_strike(actor_id, target_id, result)

        # Reactive flavor: did the target drop low?
        self._append_state_flavor(target_id, result)

        # Switch turn.
        self.turn = target_id
        self.last_action = datetime.now(timezone.utc)
        return result

    def _roll(self) -> int:
        return random.randint(1, 6)

    def _resolve_strike(self, actor_id: int, target_id: int, result: dict):
        roll = self._roll()
        result["roll"] = roll
        modifier = self.ROLL_MODIFIERS[roll]

        self._gain_energy(actor_id, mechanics.STRIKE_ENERGY)

        if modifier == 0:
            self.momentum[actor_id] = 0
            result["missed"] = True
            line = f"💨 **{self.name_of(actor_id)}** rolled a 1 and missed!"
            result["lines"].append(line)
            self._add_log(line)
            return

        crit = mechanics.roll_is_crit(self.get_card(actor_id), roll)
        base = self._effective_attack(actor_id) * modifier
        if crit:
            base *= mechanics.get_tier(self.get_card(actor_id))["crit_mult"]

        raw = mechanics.damage_after_defense(base, self.get_card(target_id)["defense"])
        # Guard halves the incoming hit and is consumed.
        if self._consume_guard(target_id):
            raw = max(1, int(raw * mechanics.GUARD_DAMAGE_MULTIPLIER))
            result["lines"].append(
                f"✋ **{self.name_of(target_id)}** guards and absorbs the blow!")

        dealt = self._deal_damage(target_id, raw)
        result["damage"] = dealt
        result["crit"] = crit
        self.momentum[actor_id] += 1

        crit_tag = " " + mechanics.flavor_text("crit") if crit else ""
        line = (f"⚔️ **{self.name_of(actor_id)}** rolled a {roll} and hit for "
                f"**{dealt}**!{crit_tag}")
        result["lines"].append(line)
        self._add_log(line)

    def _resolve_guard(self, actor_id: int, result: dict):
        # Refresh / apply the guard status (consumed by the next incoming hit).
        self.statuses[actor_id] = [s for s in self.statuses[actor_id] if s["type"] != "guard"]
        self.statuses[actor_id].append(mechanics.make_status("guard", turns=2))
        self._gain_energy(actor_id, mechanics.GUARD_ENERGY)
        # Small self-shield from bracing.
        gain = max(1, int(self.get_card(actor_id)["defense"] * 0.3))
        self.shield[actor_id] += gain
        line = (f"🛡️ **{self.name_of(actor_id)}** braces, gaining a {gain} shield "
                f"and charging energy.")
        result["lines"].append(line)
        self._add_log(line)

    def _resolve_special(self, actor_id: int, target_id: int, result: dict):
        card = self.get_card(actor_id)
        spec = mechanics.get_special(card)
        potency = mechanics.get_tier(card)["potency"]
        atk = self._effective_attack(actor_id)

        self.energy[actor_id] -= mechanics.SPECIAL_COST
        result["special_name"] = spec["name"]

        roll = self._roll()
        result["roll"] = roll
        modifier = max(0.75, self.ROLL_MODIFIERS[roll])  # specials never fully whiff

        # Damage component.
        dmg = 0
        if spec.get("damage_mult"):
            crit = spec.get("guaranteed_crit", False) or mechanics.roll_is_crit(card, roll)
            base = atk * spec["damage_mult"] * modifier
            if crit:
                base *= mechanics.get_tier(card)["crit_mult"]
            raw = mechanics.damage_after_defense(base, self.get_card(target_id)["defense"])
            if self._consume_guard(target_id):
                raw = max(1, int(raw * mechanics.GUARD_DAMAGE_MULTIPLIER))
            dmg = self._deal_damage(target_id, raw)
            result["damage"] = dmg
            result["crit"] = crit

        # Status / utility components (scaled by rarity potency).
        if spec.get("burn"):
            mag = max(1, int(atk * spec["burn"]["magnitude"] * potency))
            self._apply_status(target_id, "burn", spec["burn"]["turns"], mag)
        if spec.get("weaken"):
            self._apply_status(target_id, "weaken", spec["weaken"]["turns"],
                               spec["weaken"]["magnitude"])
        if spec.get("stun"):
            self._apply_status(target_id, "stun", spec["stun"] + 1, 0)
        if spec.get("shield"):
            self.shield[actor_id] += max(1, int(atk * spec["shield"] * potency))
        if spec.get("heal"):
            heal = max(1, int(atk * spec["heal"] * potency))
            self.hp[actor_id] = min(card["hp"], self.hp[actor_id] + heal)
        if spec.get("energy_refund"):
            self.energy[actor_id] = min(mechanics.MAX_ENERGY,
                                        self.energy[actor_id] + spec["energy_refund"])

        self.momentum[actor_id] += 1
        dmg_tag = f" for **{dmg}**" if dmg else ""
        line = f"{spec['emoji']} **{self.name_of(actor_id)}** unleashes **{spec['name']}**{dmg_tag}!"
        result["lines"].append(line)
        self._add_log(line)

    # --- Status utilities ----------------------------------------------

    def _apply_status(self, target_id: int, stype: str, turns: int, magnitude: float):
        # Refresh an existing status of the same type instead of stacking.
        self.statuses[target_id] = [s for s in self.statuses[target_id] if s["type"] != stype]
        self.statuses[target_id].append(mechanics.make_status(stype, turns, magnitude))

    def _consume_guard(self, target_id: int) -> bool:
        for s in list(self.statuses[target_id]):
            if s["type"] == "guard":
                self.statuses[target_id].remove(s)
                return True
        return False

    def _append_state_flavor(self, target_id: int, result: dict):
        if self.hp[target_id] <= 0:
            return
        max_hp = self.get_card(target_id)["hp"]
        if max_hp > 0 and self.hp[target_id] / max_hp <= 0.25:
            line = mechanics.flavor_text("low_hp", self.name_of(target_id))
            result["lines"].append(line)

    # --- Back-compat -----------------------------------------------------

    def apply_roll(self, roller_id: int, roll: int) -> Tuple[int, float]:
        """Legacy Strike helper kept for back-compat. Applies a specific roll."""
        if roll not in self.ROLL_MODIFIERS:
            raise ValueError(f"Invalid roll: {roll}. Must be 1-6.")

        target_id = self.get_opponent(roller_id)
        modifier = self.ROLL_MODIFIERS[roll]
        if modifier == 0:
            damage = 0
        else:
            base = self.get_card(roller_id)["attack"] * modifier
            damage = mechanics.damage_after_defense(base, self.get_card(target_id)["defense"])
        self._deal_damage(target_id, damage)
        self.turn = target_id
        self.last_action = datetime.now(timezone.utc)
        return damage, modifier

    # --- Status / timeout queries ---------------------------------------

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
