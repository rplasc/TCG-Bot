from src.casino.rewards import CasinoResult


async def get_active_casino_modifiers(user_id: int, game: str) -> list:
    return []


def apply_casino_modifiers(base_result: CasinoResult, modifiers: list) -> CasinoResult:
    return base_result
