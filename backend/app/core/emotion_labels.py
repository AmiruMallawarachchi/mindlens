# backend/app/core/emotion_labels.py
"""
go-emotions 28-class taxonomy mapping.
Source: Demszky et al., 2020 — GoEmotions dataset.
Used to translate raw model outputs into canonical system vocabulary.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Full 28-class label list (order matches go-emotions label2id)
# ---------------------------------------------------------------------------
EMOTION_LABELS: dict[str, str] = {
    "LABEL_0":  "admiration",
    "LABEL_1":  "amusement",
    "LABEL_2":  "anger",
    "LABEL_3":  "annoyance",
    "LABEL_4":  "approval",
    "LABEL_5":  "caring",
    "LABEL_6":  "confusion",
    "LABEL_7":  "curiosity",
    "LABEL_8":  "desire",
    "LABEL_9":  "disappointment",
    "LABEL_10": "disapproval",
    "LABEL_11": "disgust",
    "LABEL_12": "embarrassment",
    "LABEL_13": "excitement",
    "LABEL_14": "fear",
    "LABEL_15": "gratitude",
    "LABEL_16": "grief",
    "LABEL_17": "joy",
    "LABEL_18": "love",
    "LABEL_19": "nervousness",
    "LABEL_20": "optimism",
    "LABEL_21": "pride",
    "LABEL_22": "realization",
    "LABEL_23": "relief",
    "LABEL_24": "remorse",
    "LABEL_25": "sadness",
    "LABEL_26": "surprise",
    "LABEL_27": "neutral",
}

# ---------------------------------------------------------------------------
# Groupings for downstream logic
# ---------------------------------------------------------------------------

POSITIVE_EMOTIONS: set[str] = {
    "admiration", "amusement", "approval", "caring", "curiosity",
    "desire", "excitement", "gratitude", "joy", "love",
    "optimism", "pride", "realization", "relief", "surprise",
}

NEGATIVE_EMOTIONS: set[str] = {
    "anger", "annoyance", "confusion", "disappointment",
    "disapproval", "disgust", "embarrassment", "fear",
    "grief", "nervousness", "remorse", "sadness",
}

AMBIGUOUS_EMOTIONS: set[str] = {
    "neutral",  # context-dependent
    "surprise", # can be positive or negative
}

# ---------------------------------------------------------------------------
# Severity weights: how strongly each emotion contributes to distress
# Higher = more clinically concerning
# ---------------------------------------------------------------------------
EMOTION_SEVERITY_WEIGHTS: dict[str, float] = {
    "grief":        1.00,
    "fear":         0.95,
    "sadness":      0.90,
    "anger":        0.85,
    "remorse":      0.85,
    "disgust":      0.80,
    "disappointment": 0.75,
    "nervousness":  0.70,
    "embarrassment": 0.65,
    "annoyance":    0.50,
    "confusion":    0.45,
    "disapproval":  0.40,
    # positive emotions default to 0.0 (no distress contribution)
}

# ---------------------------------------------------------------------------
# Condition-adjacent emotion clusters
# Used by the modality router to guess which therapeutic frame fits best
# ---------------------------------------------------------------------------
EMOTION_TO_CONDITION_HINT: dict[str, str] = {
    "fear":         "anxiety",
    "nervousness":  "anxiety",
    "sadness":      "depression",
    "grief":        "depression",
    "remorse":      "depression",
    "anger":        "stress",
    "annoyance":    "stress",
    "disgust":      "stress",
    "disappointment": "depression",
}


def get_emotion_name(label_id: str) -> str:
    """Map raw HF label ID to canonical emotion name."""
    return EMOTION_LABELS.get(label_id, "unknown")


def is_negative(emotion: str) -> bool:
    return emotion in NEGATIVE_EMOTIONS


def severity_weight(emotion: str) -> float:
    return EMOTION_SEVERITY_WEIGHTS.get(emotion, 0.0)