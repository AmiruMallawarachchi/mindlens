"""Mapping between go-emotions 28-output and therapy routing.
"""

GO_EMOTIONS_LABELS = {
    0: "admiration",
    1: "amusement",
    2: "anger",
    3: "annoyance",
    4: "approval",
    5: "caring",
    6: "confusion",
    7: "curiosity",
    8: "desire",
    9: "disappointment",
    10: "disgust",
    11: "embarrassment",
    12: "excitement",
    13: "fear",
    14: "gratitude",
    15: "grief",
    16: "joy",
    17: "love",
    18: "nervousness",
    19: "optimism",
    20: "pride",
    21: "realization",
    22: "relief",
    23: "remorse",
    24: "sadness",
    25: "surprise",
    26: "neutral",
    27: "confusion",
}

# for therapy routing: which emotions triggers which interventions
NEGATIVE_EMOTIONS = {
    "sadness",
    "grief",
    "anger",
    "fear",
    "disgust",
    "dissapointment",
    "remorse",
    "embarrassment",
    "nervousness",
}

POSITIVE_EMOTIONS = {
    "joy",
    "amusement",
    "excitement",
    "gratitude",
    "relief",
    "pride",
    "optimism",
    "admiration",
    "love",
    "caring",
}

NEUTRAL_EMOTIONS = {
    "neutral",
    "approval",
    "confusion",
    "curiosity",
    "desire",
    "realization",
    "surprise",
}

# Map to core emtions for EOS
CORE_EMOTION_MAP = {
    "anger": "anger",
    "annoyance": "anger",
    "disgust": "disgust",
    "fear": "fear",
    "nervousness": "fear",
    "sadness": "sadness",
    "grief": "sadness",
    "dissapointment": "sadness",
    "remorse": "sadness",
    "joy": "joy",
    "amusement": "joy",
    "excitement": "joy",
    "gratitude": "joy",
    "relief": "joy",
    "pride": "joy",
    "optimism": "joy",
    "love": "love",
    "admiration": "love",
    "caring": "love",
    "suprise": "surprise",
    "curiosity": "surprise",
    "realization": "surprise",
    "neutral": "neutral",
    "approval": "neutral",
    "confusion": "neutral",
    "desire": "neutral",
    "embarrassment": "neutral",
}


