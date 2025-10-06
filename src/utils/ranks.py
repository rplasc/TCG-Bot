def get_rank_structure():
    # Format: (Tier name, divisions, RP per division)
    return [
        ("Bronze", 3, 100),
        ("Silver", 3, 100),
        ("Gold", 3, 100),
        ("Platinum", 3, 120),
        ("Diamond", 3, 150),
        ("Master", 1, 200),
        ("Grandmaster", 1, 0)
    ]

def calculate_rank_table():
    structure = get_rank_structure()
    rank_id = 0
    rp_map = {}

    for tier, divisions, rp_per_div in structure:
        for div in range(divisions, 0, -1):
            rp_map[rank_id] = {
                "tier": tier,
                "division": f"{div}" if divisions > 1 else None,
                "rp_to_next": rp_per_div
            }
            rank_id += 1

    return rp_map

def get_rank_display_name(rank_id):
    rank_table = calculate_rank_table()

    rank_info = rank_table.get(rank_id)
    if not rank_info:
        return "Unknown Rank"
    
    tier = rank_info["tier"]

    roman_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
    division_id = rank_info["division"]
    division = roman_map.get(division_id, division_id)

    return f"{tier} {division}" if division else tier

def calculate_user_rank(rp: int, rank_id: int) -> tuple[int, int]:
    new_rp = rp
    rank = rank_id
    rank_table = calculate_rank_table()
    max_rank_id = max(rank_table.keys())

    # Handle rank promotions
    while rank < max_rank_id and rank_table[rank]["rp_to_next"] > 0 and new_rp >= rank_table[rank]["rp_to_next"]:
        new_rp -= rank_table[rank]["rp_to_next"]
        rank += 1

    # Handle rank demotions
    while new_rp < 0 and rank > 0:
        rank -= 1
        new_rp += rank_table[rank]["rp_to_next"]

    # Cap RP within valid range for current rank
    if rank in rank_table:
        max_rp = rank_table[rank]["rp_to_next"]
        if max_rp == 0:
            new_rp = max(new_rp, 0)
        else:
            new_rp = min(max(new_rp, 0), max_rp - 1)

    return new_rp, rank

def calculate_match_multiplier(player_rank_id, opponent_rank_id):
    rank_diff = opponent_rank_id - player_rank_id
    multplier = 1.0 + (rank_diff * 0.05)
    multplier = max(0.8, 1.5)

    return round(multplier, 2)

def get_rp_change(rank_id: int, win: bool, multiplier: float = 1.0):
    rank_table = calculate_rank_table()
    rank_info = rank_table.get(rank_id)
    if not rank_info:
        return 25
    
    tier = rank_info["tier"]

    base = {
        "Bronze": 30,
        "Silver": 30,
        "Gold": 28,
        "Platinum": 25,
        "Diamond": 22,
        "Master": 18,
        "Grandmaster": 15
    }

    rp = base.get(tier, 20)

    if not win:
        return -int(rp * 0.9)
    else:
        return int(rp * multiplier)
