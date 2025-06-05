from dataclasses import dataclass, field
from src.casino.logic import draw_card

@dataclass
class BlackjackSession:
    user_id: int
    bet: int
    player_hand: list = field(default_factory=lambda: [draw_card(), draw_card()])
    dealer_hand: list = field(default_factory=lambda: [draw_card()])
    finished: bool = False
