from dataclasses import dataclass
from datetime import datetime, timezone
from src.casino.rewards import CasinoResult


@dataclass
class CasinoEvent:
    user_id: int
    event_type: str
    occurred_at: str
    payload: dict


async def emit_casino_event(event_type: str, result: CasinoResult, extra: dict | None = None) -> CasinoEvent:
    from src.database.db import update_casino_stats
    from src.economy.service import record_casino_net

    payload = {
        "game": result.game,
        "wager": result.wager,
        "payout": result.payout,
        "net": result.net,
        "outcome": result.outcome,
        **(result.metadata or {}),
        **(extra or {}),
    }
    event = CasinoEvent(
        user_id=result.user_id,
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        payload=payload,
    )

    if event_type in (
        "casino.blackjack.completed",
        "casino.slots.spin",
        "casino.roulette.spin",
    ):
        await update_casino_stats(
            result.user_id,
            wager=result.wager,
            payout=result.payout,
            blackjack_win=(result.outcome in ("win", "blackjack") and result.game == "blackjack"),
            slot_jackpot=(result.outcome == "jackpot"),
            roulette_win=(result.outcome in ("win", "exact_hit") and result.game == "roulette"),
        )
        # Track daily casino net winnings for telemetry (payouts are not reduced).
        await record_casino_net(result.user_id, result.net)

    return event
