from datetime import datetime, timezone, timedelta

def get_time_until_next_daily(last_claimed_str: str) -> str:
    last_claimed = datetime.fromisoformat(last_claimed_str).replace(tzinfo=timezone.pst)
    next_reset = last_claimed.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    now = datetime.now(timezone.pst)
    remaining = next_reset - now

    if remaining.total_seconds() <= 0:
        return None

    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def get_seconds_until_next_rotation():
    now = datetime.datetime.now(datetime.timezone.pst)
    next_rotation = now.replace(hour=15, minute=0, second=0, microsecond=0)
    if now.hour >= 15:
        next_rotation += datetime.timedelta(days=1)
    return (next_rotation - now).total_seconds()

def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def get_shop_rotation_key():
    now = datetime.datetime.now(datetime.timezone.pst)
    rotation_hour = 8  # 8 AM PST

    if now.hour < rotation_hour:
        rotation_day = now.date() - datetime.timedelta(days=1)
    else:
        rotation_day = now.date()

    return rotation_day.isoformat()