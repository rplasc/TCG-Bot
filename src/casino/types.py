from dataclasses import dataclass, field
from src.casino.logic import draw_card

@dataclass
class BlackjackSession:
    user_id: int
    bet: int
    player_hand: list = field(default_factory=lambda: [draw_card(), draw_card()])
    dealer_hand: list = field(default_factory=lambda: [draw_card(), draw_card()])
    finished: bool = False
    doubled_down: bool = False
    net: int = 0

@dataclass
class SlotSession:
    user_id: int
    wager: int = 5
    spins: int = 0
    max_spins: int = 5
    net: int = 0