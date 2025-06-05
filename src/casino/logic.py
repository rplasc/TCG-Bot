import random

CARD_VALUES = {
    "A": 11, "K": 10, "Q": 10, "J": 10,
    **{str(n): n for n in range(2, 11)}
}
CARDS = list(CARD_VALUES.keys()) * 4

def draw_card():
    return random.choice(CARDS)

def hand_total(hand):
    total = sum(CARD_VALUES[c] for c in hand)
    aces = hand.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total
