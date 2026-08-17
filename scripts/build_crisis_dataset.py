"""
Rebuild the crisis training set to match what the product actually receives.

The shipped `mindlens-crisis` classifier scored 0.82 on "I'm scared it will
not be good enough" and 0.72 on "so i need a help okay", against 0.88 for
"I want to kill myself". Six hundredths separated a student worrying about
coursework from a genuine suicide statement, so no threshold could split
them: at 0.85 the false positives vanished but a third of real crisis
messages were missed.

That is not a threshold problem. Inspecting the training data showed three
distinct mismatches between how the model was trained and how it is served:

1. Composition. The `safe` class was Reddit meme chatter ("country dancing
   illegal today tradition weird"); the `crisis` class was long, sincere,
   distressed posts. The model never saw text that was emotionally serious
   and *not* a crisis, so it learned "heartfelt equals crisis".

2. Preprocessing. The upstream dataset was lemmatized and stopword-stripped
   ("not see point anymore"). Inference passes raw user text straight
   through — there is no preprocessing anywhere in the serving path. The
   model was reading a different language than it was taught.

3. Length. Training posts ran to a median of 30 words; real chat messages
   are four to fifteen.

This script fixes all three: raw text throughout, hard negatives that are
serious without being a crisis, and short-form examples in both classes.

Every candidate negative is passed through the production safety-gate regex
first, and anything it flags is dropped rather than labelled safe. Mislabeling
a real crisis as safe is the one error this system must not learn to make, so
when a negative is doubtful it is discarded, not kept.

Run:  ../.venv/Scripts/python scripts/build_crisis_dataset.py
Out:  notebooks/data/cleaned/crisis_dataset_v2/   (raw text, balanced)
"""

from __future__ import annotations

import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from datasets import Dataset, DatasetDict, load_dataset, load_from_disk

ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "notebooks" / "data" / "cleaned"
OUT_DIR = CLEANED / "crisis_dataset_v2"

# Import the production regex so the filter here and the L1 gate at runtime
# can never drift apart.
sys.path.insert(0, str(ROOT / "backend"))
from app.agents.safety_gate import safety_gate  # noqa: E402

SEED = 20260817
random.seed(SEED)

MIN_WORDS = 3
MAX_WORDS = 300


def normalise(text: str | None) -> str | None:
    """Whitespace and unicode only. No lemmatising, no stopword removal —
    that mismatch is half of what this rebuild exists to fix."""
    if not isinstance(text, str) or not text.strip():
        return None
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    if len(words) < MIN_WORDS:
        return None
    return " ".join(words[:MAX_WORDS])


async def _flagged(text: str) -> bool:
    result = await safety_gate.evaluate(text)
    return result.is_crisis


def flags_as_crisis(text: str) -> bool:
    """True if the production L1 regex would call this a crisis."""
    import asyncio

    return asyncio.run(_flagged(text))


def build_regex_filter():
    """Compile once; evaluating 100k rows through the async gate is needless
    overhead when the patterns are the only part that matters."""
    patterns = safety_gate.crisis_patterns

    def check(text: str) -> bool:
        normalised = safety_gate._normalize(text)
        return any(p.search(normalised) for p in patterns)

    return check


# Short, product-shaped messages. The training corpus is long-form Reddit;
# these are the four-to-fifteen-word turns people actually type into a chat
# box. Both of the observed false positives are here by name — they are the
# bug this rebuild is answering, so they belong in the data.
SYNTHETIC_SAFE = [
    "so i need a help okay",
    "It is mostly that I am scared it will not be good enough.",
    "I'm scared my project won't be good enough.",
    "I need help okay",
    "can you help me",
    "I have been feeling really stressed about my final year project.",
    "I keep putting things off and I don't know why.",
    "I'm worried I will disappoint my parents.",
    "Exams are stressing me out badly.",
    "I had a rough day at work today.",
    "I feel a bit low today but nothing serious.",
    "I am tired all the time lately.",
    "I had an argument with my mum and it's bothering me.",
    "My friend cancelled on me again and it stung.",
    "Work has been overwhelming this week.",
    "I feel like I'm falling behind everyone else.",
    "I don't think I'm good at anything.",
    "I feel useless compared to my classmates.",
    "Nothing I do seems to be enough.",
    "I'm anxious about my presentation tomorrow.",
    "I can't stop overthinking everything.",
    "I feel really lonely lately.",
    "I've been sleeping badly for weeks.",
    "I feel stuck and I don't know what to do next.",
    "I'm frustrated with myself for procrastinating.",
    "Everything feels harder than it should be.",
    "I'm burnt out from studying.",
    "I feel like a failure honestly.",
    "I'm scared of what happens after graduation.",
    "I don't feel motivated to do anything today.",
    "My anxiety has been bad this week.",
    "I feel really down about my grades.",
    "I'm struggling to focus on anything.",
    "I feel like nobody understands me.",
    "I'm having a hard time coping with stress.",
    "I feel hopeless about my career prospects.",
    "I get overwhelmed really easily lately.",
    "I've been crying a lot recently.",
    "I feel empty and I don't know why.",
    "I'm just really sad today.",
]


def load_raw_base() -> tuple[list[str], list[str]]:
    """Original Kaggle SuicideWatch data with the raw `text` column intact.

    The dataset the shipped model used kept only the lemmatized version.
    Ram07 carries both, so the raw side is recoverable without re-scraping.
    """
    print("Loading Ram07/Detection-for-Suicide (raw text)...")
    ds = load_dataset("Ram07/Detection-for-Suicide", split="train")
    crisis, safe = [], []
    for row in ds:
        text = normalise(row.get("text"))
        if not text:
            continue
        cls = str(row.get("class", "")).strip().lower()
        if cls == "suicide":
            crisis.append(text)
        elif cls == "non-suicide":
            safe.append(text)
    print(f"  crisis {len(crisis)}  safe {len(safe)}")
    return crisis, safe


def load_local(name: str):
    d = load_from_disk(str(CLEANED / name))
    return d["train"] if hasattr(d, "keys") and "train" in d else d


def collect_hard_negatives(is_crisis_regex) -> dict[str, list[str]]:
    """Emotionally serious text that is explicitly not a crisis.

    This is the class the shipped model never saw. Anything the production
    regex flags is dropped — a real crisis mislabelled as safe is the one
    error worth being paranoid about, so doubtful rows are discarded rather
    than kept.
    """
    pools: dict[str, list[str]] = {}

    # Explicit non-crisis labels from a depression-severity corpus. The
    # safest source here: someone else already made the crisis judgement.
    dep = load_local("dep_severity")
    pools["dep_severity"] = [
        t
        for raw, c in zip(dep["text"], dep["crisis_label"], strict=True)
        if str(c) == "0" and (t := normalise(raw)) and not is_crisis_regex(t)
    ]

    # Short emotional utterances — fixes the length mismatch as well as the
    # composition one.
    dair = load_local("dair_emotion")
    pools["dair_emotion"] = [
        t for raw in dair["text"] if (t := normalise(raw)) and not is_crisis_regex(t)
    ]

    # Mental-health subreddit posts. These carry genuine anxiety, PTSD and
    # depression without being suicidal — but they come from communities
    # where real crisis posts also live, so the regex filter matters most
    # here.
    for name in ("reddit_mh_posts", "ourafla_mh"):
        ds = load_local(name)
        pools[name] = [
            t for raw in ds["text"] if (t := normalise(raw)) and not is_crisis_regex(t)
        ]

    # Therapy-seeking questions: serious, help-seeking, not crisis. This is
    # the exact register of "so i need a help okay".
    cc = load_local("counselchat")
    pools["counselchat"] = [
        t for raw in cc["question"] if (t := normalise(raw)) and not is_crisis_regex(t)
    ]

    pools["synthetic_short"] = [
        t for raw in SYNTHETIC_SAFE if (t := normalise(raw)) and not is_crisis_regex(t)
    ]

    return pools


def main() -> None:
    is_crisis_regex = build_regex_filter()

    crisis, base_safe = load_raw_base()
    pools = collect_hard_negatives(is_crisis_regex)

    print("\nHard-negative pools (post regex filter):")
    for name, rows in pools.items():
        print(f"  {name:<18} {len(rows):>7}")

    # Cap the meme-heavy original safe class so hard negatives are not
    # drowned out — that imbalance is what taught the model "serious equals
    # crisis" in the first place.
    hard = [t for name, rows in pools.items() if name != "synthetic_short" for t in rows]
    random.shuffle(hard)
    random.shuffle(base_safe)

    n_crisis = len(crisis)
    n_hard = min(len(hard), int(n_crisis * 0.55))
    n_base = max(0, n_crisis - n_hard)
    n_base = min(n_base, len(base_safe))

    # Short synthetic turns are upsampled: they are few, and they represent
    # the exact input distribution the deployed product sees.
    synthetic = pools["synthetic_short"] * 40

    safe = hard[:n_hard] + base_safe[:n_base] + synthetic
    random.shuffle(safe)

    print("\nFinal composition:")
    print(f"  crisis            {len(crisis):>7}")
    print(f"  safe (hard)       {n_hard:>7}")
    print(f"  safe (original)   {n_base:>7}")
    print(f"  safe (synthetic)  {len(synthetic):>7}")
    print(f"  safe total        {len(safe):>7}")

    rows = [{"text": t, "label": 1, "label_name": "crisis"} for t in crisis]
    rows += [{"text": t, "label": 0, "label_name": "safe"} for t in safe]
    random.shuffle(rows)

    n = len(rows)
    n_train, n_val = int(n * 0.8), int(n * 0.1)
    splits = DatasetDict(
        {
            "train": Dataset.from_list(rows[:n_train]),
            "validation": Dataset.from_list(rows[n_train : n_train + n_val]),
            "test": Dataset.from_list(rows[n_train + n_val :]),
        }
    )

    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    splits.save_to_disk(str(OUT_DIR))

    print(f"\nSaved to {OUT_DIR}")
    for name, split in splits.items():
        counts = Counter(split["label"])
        lens = [len(t.split()) for t in split["text"][:5000]]
        median = sorted(lens)[len(lens) // 2] if lens else 0
        print(f"  {name:<11} {len(split):>7}  labels={dict(counts)}  median_words={median}")


if __name__ == "__main__":
    main()
