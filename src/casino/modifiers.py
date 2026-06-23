from src.casino.rewards import CasinoResult
from src.events.service import casino_payout_multiplier


async def get_active_casino_modifiers(user_id: int, game: str) -> list:
    """Return active casino modifiers for telemetry/metadata.

    The payout multiplier is applied to the awarded coins inside each game (before
    the award call); this just surfaces the active multiplier so it lands in the
    result metadata. Returns an empty list when no event affects ``game``.
    """
    mult = casino_payout_multiplier(game)
    if mult != 1.0:
        return [{"type": "event_payout_mult", "value": mult}]
    return []


def apply_casino_modifiers(base_result: CasinoResult, modifiers: list) -> CasinoResult:
    """Record modifier metadata on the result. Does NOT award coins."""
    for m in modifiers:
        if m["type"] == "event_payout_mult":
            base_result.metadata["event_payout_mult"] = m["value"]
    return base_result
