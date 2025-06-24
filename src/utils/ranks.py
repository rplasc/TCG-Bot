def get_rank_structure():
    # Format: (Tier name, divisions, RP per division)
    return [
        ("Bronze", 3, 100),
        ("Silver", 3, 100),
        ("Gold", 3, 100),
        ("Platinum", 3, 120),
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

def calculate_user_rank(rp: int, rank_id: int) -> int:
    new_rp = rp
    rank = rank_id
    rank_table = calculate_rank_table()

    while rank < max(rank_table.keys()) and rp >= rank_table[rank]["rp_to_next"]:
        new_rp -= rank_table[rank]["rp_to_next"]
        rank += 1

    while new_rp < 0 and rank > 0:
        rank -= 1
        new_rp += rank_table[rank]["rp_to_next"]

    max_rp = rank_table[rank]["rp_to_next"]
    new_rp = min(max(new_rp, 0), max_rp)

    return new_rp, rank