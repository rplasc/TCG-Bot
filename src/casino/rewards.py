from dataclasses import dataclass, field


@dataclass
class CasinoResult:
    user_id: int
    game: str
    wager: int
    payout: int
    net: int
    outcome: str
    metadata: dict = field(default_factory=dict)


def build_result_footer(wager: int, payout: int, net: int, balance: int) -> str:
    net_str = f"+{net}" if net >= 0 else str(net)
    return f"Wager: {wager} | Payout: {payout} | Net: {net_str} | 💰 Balance: {balance}"
