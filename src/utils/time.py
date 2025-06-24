import zoneinfo
from datetime import datetime, timedelta
from typing import Tuple

def get_time_until_next_daily(last_claimed_str: str) -> str:
    last_claimed = datetime.fromisoformat(last_claimed_str).replace(tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles"))
    next_reset = last_claimed.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    now = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    remaining = next_reset - now

    if remaining.total_seconds() <= 0:
        return None

    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def get_seconds_until_next_rotation():
    now = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    next_rotation = now.replace(hour=15, minute=0, second=0, microsecond=0)
    if now.hour >= 15:
        next_rotation += datetime.timedelta(days=1)
    return (next_rotation - now).total_seconds()

def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def get_shop_rotation_key():
    now = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    rotation_hour = 8  # 8 AM PST

    if now.hour < rotation_hour:
        rotation_day = now.date() - datetime.timedelta(days=1)
    else:
        rotation_day = now.date()

    return rotation_day.isoformat()

def get_current_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def parse_date_str(date_str: str) -> datetime.date:
    return datetime.fromisoformat(date_str).date()

def is_consecutive_day(last_date: str, current_date: str) -> bool:
    try:
        last = parse_date_str(last_date)
        current = parse_date_str(current_date)
        return (current - last).days == 1
    except (ValueError, AttributeError):
        return False

def is_same_day(date1: str, date2: str) -> bool:
    try:
        return parse_date_str(date1) == parse_date_str(date2)
    except (ValueError, AttributeError):
        return False

def get_streak_bonus(streak_count: int) -> Tuple[int, int]:
    # Base bonus increases every 7 days
    week_multiplier = (streak_count - 1) // 7 + 1
    
    # Special bonuses for milestones
    milestone_bonus = 0
    if streak_count % 30 == 0:  # Monthly milestone
        milestone_bonus = 100
    elif streak_count % 7 == 0:  # Weekly milestone
        milestone_bonus = 25
    
    bonus_coins = min(week_multiplier * 5 + milestone_bonus, 150)
    return bonus_coins