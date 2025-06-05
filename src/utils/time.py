from datetime import datetime, timezone, timedelta

def get_time_until_next_daily(last_claimed_str: str) -> str:
    last_claimed = datetime.fromisoformat(last_claimed_str).replace(tzinfo=timezone.utc)
    next_reset = last_claimed.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    now = datetime.now(timezone.utc)
    remaining = next_reset - now

    if remaining.total_seconds() <= 0:
        return None

    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return f"{hours}h {minutes}m"
