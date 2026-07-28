#!/usr/bin/env python3
"""
MindLens Distortion Model Training Pipeline
============================================
Trains a 10-class multi-label cognitive distortion classifier on
CounselChat data + synthetic augmentation for missing classes.

Base model: roberta-base
Task: Multi-label classification (10 distortion classes)
Target: Macro F1 > 0.72

Usage:
    cd backend
    python ../scripts/train_distortion_model.py

Requirements (already in venv):
    transformers, datasets, torch, accelerate, scikit-learn, numpy
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    get_linear_schedule_with_warmup,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LABELS = [
    "catastrophizing",
    "mind_reading",
    "all_or_nothing",
    "personalization",
    "overgeneralization",
    "emotional_reasoning",
    "should_statements",
    "jumping_to_conclusions",
    "magnification",
    "mental_filter",
]

NUM_LABELS = len(LABELS)

# Text label → index mapping (handles British/American spelling variants)
TEXT_LABEL_MAP = {
    "catastrophizing": 0,
    "catastrophising": 0,  # British spelling variant
    "mind_reading": 1,
    "all_or_nothing": 2,
    "personalization": 3,
    "personalisation": 3,  # British variant
    "overgeneralization": 4,
    "overgeneralisation": 4,  # British variant
    "emotional_reasoning": 5,
    "should_statements": 6,
    "should_statement": 6,
    "jumping_to_conclusions": 7,
    "fortune_telling": 7,  # Semantically equivalent
    "magnification": 8,
    "magnifying": 8,
    "mental_filter": 9,
    "filtering": 9,
    "disqualifying_the_positive": 9,  # Related to mental filtering
}

MODEL_NAME = "roberta-base"
MAX_LENGTH = 256
BATCH_SIZE = 8
GRADIENT_ACCUMULATION_STEPS = 4  # Effective batch = 32 (RTX 2050 friendly)
LEARNING_RATE = 2e-5
WARMUP_RATIO = 0.1
NUM_EPOCHS = 15
WEIGHT_DECAY = 0.01
SEED = 42

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

OUTPUT_DIR = Path("models/distortion_model")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_PATH = Path("notebooks/data/cleaned/counselchat")

# Number of synthetic examples per missing/sparse class
SYNTHETIC_PER_CLASS = 50

# ---------------------------------------------------------------------------
# Synthetic data templates (CBT-informed examples for each missing class)
# ---------------------------------------------------------------------------

SYNTHETIC_TEMPLATES: dict[str, list[str]] = {
    "all_or_nothing": [
        "If I don't get a perfect score, I'm a total failure. Anything less than 100% means I'm worthless.",
        "Either I'm the best at this or I'm completely incompetent. There's no middle ground.",
        "I messed up one thing at work, so the whole project is ruined. I'm a complete failure.",
        "My friend didn't reply to my text immediately, so she must hate me now. Our friendship is over.",
        "I ate one cookie and broke my diet, so I might as well eat the whole box. I've already ruined everything.",
        "I got one question wrong on the test, so I failed completely. I never do anything right.",
        "If I can't do this perfectly, I shouldn't even try at all. It's pointless unless it's flawless.",
        "My partner and I had one argument, so our relationship is doomed. We're either perfect or nothing.",
        "I made one mistake in the presentation, so the whole thing was terrible. I'm never good at anything.",
        "Either people love me completely or they hate me. There's no such thing as partial acceptance.",
    ],
    "personalization": [
        "My parents are fighting again, and it's definitely my fault. If I were a better child, they wouldn't argue.",
        "My friend seemed upset today, and I know it's because I said something wrong last week.",
        "The team lost the game, and it's entirely because I missed that one shot. I ruined it for everyone.",
        "My boss looked stressed in the meeting, and I just know she's disappointed in me specifically.",
        "My partner is in a bad mood, and I must have done something to cause it. It's always my fault somehow.",
        "My colleague didn't say good morning to me, so I must have offended them. They're mad at me.",
        "The restaurant was out of my favorite dish, and I feel like it's because I shouldn't have come here.",
        "My friend cancelled our plans, and I know it's because they secretly don't want to be around me.",
        "The meeting ended awkwardly, and I'm sure everyone is blaming me for how it went.",
        "My neighbor didn't wave back, so I must have done something to upset them. They hate me now.",
    ],
    "magnification": [
        "I made a tiny typo in my email, and now I'm convinced my boss will fire me over it. It's catastrophic.",
        "My friend took 3 hours to reply, and I'm terrified she's abandoning me. This is the end of everything.",
        "I stumbled slightly during my speech, and now I'm sure everyone thinks I'm completely incompetent.",
        "I got a minor criticism on my work, and it's all I can think about. It feels like my whole career is over.",
        "I have a small headache, and I'm convinced it's something seriously wrong with my brain.",
        "I didn't get invited to one party, and it feels like I'm completely excluded from everything in life.",
        "My bank balance is slightly low this week, and I'm terrified I'll end up homeless and destitute.",
        "I got a B+ on one assignment, and now I feel like I'll never get into grad school. Everything is ruined.",
        "My partner said my cooking was 'fine,' and now I'm sure they think I'm terrible at everything.",
        "I made one small mistake at the gym, and now I'm convinced everyone is judging me as a complete loser.",
    ],
    "mental_filter": [
        "I got 9 compliments and 1 criticism at work, but all I can think about is that one criticism.",
        "My presentation went well except for one tiny part, but that's the only thing I remember about it.",
        "I had a great day with friends, but one awkward moment is all I can focus on now.",
        "My relationship is mostly good, but I obsess over the one time we argued last month.",
        "I completed most of my tasks today, but I can't stop thinking about the one I didn't finish.",
        "The trip was amazing overall, but I only remember the one bad hotel experience.",
        "My teacher praised me several times, but the one correction they gave is what sticks in my mind.",
        "I cooked a great dinner, but one dish was slightly overcooked, and that's all I can think about.",
        "My performance review was mostly positive, but I'm fixated on the one area for improvement.",
        "I had a fun conversation with someone, but I keep replaying the one awkward thing I said.",
    ],
    "overgeneralization": [
        "I failed one exam, so I'll never pass anything in my life. I'm just bad at school.",
        "One person rejected me, so everyone will always reject me. Nobody ever likes me.",
        "I got rejected from one job, so I'll never get hired anywhere. The whole system is against me.",
        "I had one bad experience with a therapist, so therapy never works for anyone.",
        "One person was rude to me today, so everyone in this city is hostile and mean.",
        "I failed at one diet, so I'll never be able to lose weight. I always fail at everything.",
        "My last relationship ended badly, so all relationships are doomed. I'll never find love.",
        "I got one bad grade, so I'm terrible at this subject. I always fail at academics.",
        "One friend betrayed me, so I can't trust anyone. Everyone always lets me down eventually.",
        "I had a panic attack in one situation, so I'll always have panic attacks everywhere.",
    ],
    "emotional_reasoning": [
        "I feel like a failure, so I must be a failure. My feelings are the truth.",
        "I feel like nobody cares about me, so it must be true that nobody cares.",
        "I feel worthless right now, so I am worthless. If I feel it, it must be reality.",
        "I feel like my partner is cheating, so they must be cheating. My gut never lies.",
        "I feel anxious about this decision, so it must be the wrong choice. My anxiety is telling me the truth.",
        "I feel ugly today, so I must actually be ugly. My feelings define reality.",
        "I feel like I'm not good enough, so I must not be good enough. My emotions are valid evidence.",
        "I feel like everyone is judging me, so they must be judging me. I can feel their eyes on me.",
        "I feel like this will never get better, so it never will. My hopelessness is proof of the future.",
        "I feel like I don't deserve this opportunity, so I must not deserve it. My feelings are facts.",
    ],
    "should_statements": [
        "I should always be productive. If I'm resting, I'm being lazy and wasting my life.",
        "I should never feel anxious. If I do, I'm weak and there's something wrong with me.",
        "I should always be there for everyone. If I say no, I'm a terrible friend.",
        "I should have my life figured out by now. I'm 25 and I should have everything together.",
        "I should never make mistakes. If I do, I'm failing at the most basic level of being human.",
        "I should always be happy. If I'm not, I'm doing something fundamentally wrong with my life.",
        "I should be able to handle this on my own. If I need help, I'm weak and pathetic.",
        "I should never feel angry. Good people don't get angry, and I should be a good person.",
        "I should have known better. I should have predicted this outcome. It's my fault for not seeing it coming.",
        "I should be further along in my career by now. Everyone else my age is doing better than me.",
    ],
    "jumping_to_conclusions": [
        "My friend didn't text back, so they're obviously mad at me. I must have done something wrong.",
        "My boss wants to meet with me tomorrow, so I must be getting fired. There's no other reason.",
        "My partner seemed distant, so they're definitely thinking about breaking up with me.",
        "I didn't get the job offer yet, so they must have chosen someone else. I already failed.",
        "My friend posted a photo with someone else, so they've replaced me. I'm not important to them anymore.",
        "The doctor wants to see me in person, so it must be terrible news. I already know the diagnosis.",
        "My date cancelled last minute, so they must have found someone better. I'm not worth their time.",
        "My professor didn't reply to my email, so they must think my question is stupid. They don't respect me.",
        "My roommate was quiet when I came home, so they must be angry at me. I did something wrong.",
        "The test results are taking longer than usual, so they must have found something serious. I already know.",
    ],
    "catastrophizing": [
        "I have a slight headache, and I'm convinced it's a brain tumor. This is going to kill me.",
        "If I fail this exam, I'll never get into university, and my entire life will be ruined forever.",
        "My partner didn't reply for an hour, so they must have been in a terrible accident. I need to call hospitals.",
        "If I lose this job, I'll never work again, and I'll end up homeless and alone on the streets.",
        "I made a small mistake in my application, so I'll definitely be rejected from every school I applied to.",
        "My throat feels slightly scratchy, so I'm probably dying of some rare disease. I should write a will.",
        "If this relationship ends, I'll never find love again. I'll die alone and nobody will care.",
        "I got one bad review at work, so I'm definitely getting fired, and then I'll lose my apartment.",
        "My flight is delayed, and now I'll miss my connection, and then I'll be stranded in a foreign country forever.",
        "If I don't get this promotion, my career is completely over. I'll never advance professionally again.",
    ],
    "mind_reading": [
        "My friend didn't invite me to the party, so they must think I'm boring and annoying.",
        "My boss sighed during my presentation, so she's definitely thinking I'm incompetent and wasting her time.",
        "My partner said 'I'm fine,' but I know they're actually furious with me and just hiding it.",
        "My colleague looked at me strangely, so she must be thinking about how I embarrassed myself last week.",
        "My teacher said my work was 'interesting,' but I know she meant it's terrible and she's being nice.",
        "My friend took a while to reply, so they must be annoyed by me and wishing I'd stop messaging them.",
        "My date smiled at the waiter, so they must be thinking about how much better looking the waiter is than me.",
        "My coworker didn't laugh at my joke, so they must think I'm not funny at all and probably weird.",
        "My parent said 'do whatever you want,' but I know they actually think I'm making a terrible decision.",
        "My friend posted a photo without me, so they must be trying to send me a message that I'm not welcome.",
    ],
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def count_labels(labels_array: np.ndarray) -> dict[str, int]:
    """Count per-label occurrences."""
    counts = {}
    for i, label in enumerate(LABELS):
        counts[label] = int(labels_array[:, i].sum())
    return counts


# ---------------------------------------------------------------------------
# Data loading and fixing
# ---------------------------------------------------------------------------

def load_and_fix_counselchat() -> dict[str, dict[str, Any]]:
    """
    Load CounselChat data, fix the broken distortion_vector encoding,
    and generate synthetic examples for missing classes.
    """
    from datasets import load_from_disk

    ds = load_from_disk(str(DATA_PATH))
    splits: dict[str, Any] = {}

    for split in ["train", "validation", "test"]:
        if split not in ds:
            continue

        split_data = ds[split]
        fixed = []
        for i in range(len(split_data)):
            text = split_data[i]["text"]
            text_labels = split_data[i]["cognitive_distortions"]

            # Rebuild the vector from text labels
            vector = [0] * NUM_LABELS
            for tl in text_labels:
                tl_clean = tl.strip().lower()
                if tl_clean in TEXT_LABEL_MAP:
                    idx = TEXT_LABEL_MAP[tl_clean]
                    vector[idx] = 1

            fixed.append({
                "text": text,
                "labels": vector,
                "source": "counselchat",
            })

        splits[split] = fixed

    # Print original stats
    print("=" * 60)
    print("Original CounselChat data (after vector fix):")
    for split, data in splits.items():
        arr = np.array([d["labels"] for d in data])
        counts = count_labels(arr)
        print(f"\n{split}: {len(data)} samples")
        for label, count in counts.items():
            print(f"  {label}: {count}")

    return splits


def generate_synthetic_examples() -> list[dict[str, Any]]:
    """Generate synthetic training examples for underrepresented classes."""
    examples = []
    for label_name, templates in SYNTHETIC_TEMPLATES.items():
        label_idx = LABELS.index(label_name)
        for template in templates:
            vector = [0] * NUM_LABELS
            vector[label_idx] = 1
            examples.append({
                "text": template,
                "labels": vector,
                "source": "synthetic",
            })
    return examples


# ---------------------------------------------------------------------------
# PyTorch Dataset
# ---------------------------------------------------------------------------

class DistortionDataset(Dataset):
    def __init__(
        self,
        texts: list[str],
        labels: list[list[int]],
        tokenizer,
        max_length: int = MAX_LENGTH,
    ):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        text = self.texts[idx]
        labels = torch.tensor(self.labels[idx], dtype=torch.float32)

        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": labels,
        }


# ---------------------------------------------------------------------------
# Training metrics (compute for Trainer)
# ---------------------------------------------------------------------------

def compute_metrics(eval_pred) -> dict[str, float]:
    """Compute multi-label classification metrics."""
    logits, labels = eval_pred
    probs = torch.sigmoid(torch.tensor(logits)).numpy()
    preds = (probs > 0.5).astype(int)
    labels = labels.astype(int)

    # Per-label F1
    f1_per_label = f1_score(labels, preds, average=None, zero_division=0)
    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    micro_f1 = f1_score(labels, preds, average="micro", zero_division=0)
    weighted_f1 = f1_score(labels, preds, average="weighted", zero_division=0)

    macro_precision = precision_score(labels, preds, average="macro", zero_division=0)
    macro_recall = recall_score(labels, preds, average="macro", zero_division=0)

    # Print per-label breakdown
    print("\nPer-label F1:")
    for i, label in enumerate(LABELS):
        print(f"  {label}: {f1_per_label[i]:.3f}  (precision={precision_score(labels[:, i], preds[:, i], zero_division=0):.3f}, recall={recall_score(labels[:, i], preds[:, i], zero_division=0):.3f})")
    print(f"Macro F1: {macro_f1:.3f}")
    print(f"Micro F1: {micro_f1:.3f}")
    print(f"Weighted F1: {weighted_f1:.3f}")

    return {
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "weighted_f1": weighted_f1,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
    }


# ---------------------------------------------------------------------------
# Class-weighted loss (for handling imbalance)
# ---------------------------------------------------------------------------

class WeightedBCELossTrainer(Trainer):
    """Trainer with per-label class weighting in BCE loss."""

    def __init__(self, class_weights: torch.Tensor | None = None, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        loss_fct = nn.BCEWithLogitsLoss(
            weight=self.class_weights.to(logits.device) if self.class_weights is not None else None,
            pos_weight=None,
        )
        loss = loss_fct(logits, labels)

        return (loss, outputs) if return_outputs else loss


# ---------------------------------------------------------------------------
# Main training pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    set_seed(SEED)
    print("=" * 60)
    print("MindLens Distortion Model Training Pipeline")
    print(f"Device: {DEVICE}")
    print(f"Model: {MODEL_NAME}")
    print(f"Labels: {NUM_LABELS}")
    print("=" * 60)

    # 1. Load and fix data
    print("\n[1/6] Loading and fixing CounselChat data...")
    splits = load_and_fix_counselchat()

    # 2. Add synthetic examples to training set
    print("\n[2/6] Generating synthetic training examples...")
    synthetic_examples = generate_synthetic_examples()
    print(f"Generated {len(synthetic_examples)} synthetic examples.")
    splits["train"].extend(synthetic_examples)

    # Print final stats
    all_train_labels = np.array([d["labels"] for d in splits["train"]])
    print("\nFinal training distribution:")
    counts = count_labels(all_train_labels)
    for label, count in counts.items():
        print(f"  {label}: {count}")
    print(f"Total training: {len(splits['train'])}")
    print(f"Validation: {len(splits['validation'])}")
    print(f"Test: {len(splits['test'])}")

    # 3. Compute class weights for imbalance
    print("\n[3/6] Computing class weights...")
    pos_counts = all_train_labels.sum(axis=0)
    neg_counts = len(all_train_labels) - pos_counts
    # Weight: inverse frequency normalized
    class_weights = torch.tensor(
        (neg_counts / (pos_counts + 1e-6)) ** 0.5,
        dtype=torch.float32,
    )
    print("Class weights:")
    for i, label in enumerate(LABELS):
        print(f"  {label}: {class_weights[i]:.3f}")

    # 4. Tokenizer and datasets
    print("\n[4/6] Preparing tokenized datasets...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_dataset = DistortionDataset(
        texts=[d["text"] for d in splits["train"]],
        labels=[d["labels"] for d in splits["train"]],
        tokenizer=tokenizer,
    )
    val_dataset = DistortionDataset(
        texts=[d["text"] for d in splits["validation"]],
        labels=[d["labels"] for d in splits["validation"]],
        tokenizer=tokenizer,
    )
    test_dataset = DistortionDataset(
        texts=[d["text"] for d in splits["test"]],
        labels=[d["labels"] for d in splits["test"]],
        tokenizer=tokenizer,
    )

    # 5. Model
    print("\n[5/6] Loading model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
        id2label={i: label for i, label in enumerate(LABELS)},
        label2id={label: i for i, label in enumerate(LABELS)},
    )

    # 6. Training arguments
    print("\n[6/6] Starting training...")
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_strategy="epoch",
        logging_steps=10,
        fp16=torch.cuda.is_available(),  # Mixed precision for RTX 2050
        dataloader_num_workers=0,
        seed=SEED,
        report_to=["none"],  # No wandb/tensorboard by default
    )

    trainer = WeightedBCELossTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        class_weights=class_weights,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=4)],
    )

    trainer.train()

    # Final evaluation on test set
    print("\n" + "=" * 60)
    print("Final evaluation on test set:")
    print("=" * 60)
    test_results = trainer.evaluate(test_dataset)
    print(f"\nTest results: {json.dumps(test_results, indent=2)}")

    # Save model
    print(f"\nSaving model to {OUTPUT_DIR}...")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # Save label mapping
    with open(OUTPUT_DIR / "label_mapping.json", "w") as f:
        json.dump({
            "labels": LABELS,
            "id2label": {i: label for i, label in enumerate(LABELS)},
            "label2id": {label: i for i, label in enumerate(LABELS)},
        }, f, indent=2)

    print("\n✅ Training complete!")
    print(f"Model saved to: {OUTPUT_DIR}")
    print(f"To upload to HuggingFace Hub:")
    print(f"  huggingface-cli login")
    print(f"  python -c \"from transformers import AutoModel; AutoModel.from_pretrained('{OUTPUT_DIR}').push_to_hub('AmiruMallawarachchi/mindlens-distortion')\"")

    # Return key metrics for automated evaluation
    return {
        "macro_f1": test_results.get("eval_macro_f1", 0.0),
        "micro_f1": test_results.get("eval_micro_f1", 0.0),
        "weighted_f1": test_results.get("eval_weighted_f1", 0.0),
    }


if __name__ == "__main__":
    results = main()
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS: {json.dumps(results, indent=2)}")
    print(f"{'='*60}")
