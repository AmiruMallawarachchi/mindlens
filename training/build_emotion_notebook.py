"""Generate training/emotion-classifier-multilabel.ipynb.

The notebook is generated rather than hand-edited so the 28 label names stay
provably identical to `backend/app/core/emotion_labels.py`. If that file
changes, regenerate — do not edit the .ipynb by hand.

Usage:
    python training/build_emotion_notebook.py            # smoke run (1%, 1 epoch)
    python training/build_emotion_notebook.py --full     # full training run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.emotion_labels import EMOTION_LABELS  # noqa: E402

LABELS = [EMOTION_LABELS[f"LABEL_{i}"] for i in range(28)]
assert len(LABELS) == 28, "expected the 28-class GoEmotions taxonomy"
assert LABELS[-1] == "neutral", "neutral must remain the last label"

OUT = ROOT / "training" / "emotion-classifier-multilabel.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def build(smoke: bool) -> dict:
    cells = [
        md(
            f"""# MindLens — Emotion Classifier (28-class multi-label GoEmotions)

Replaces the 6-class single-label model with the 28-class **multi-label**
classifier the system actually requires.

**Why multi-label matters here.** The orchestrator calls this pipeline with
`top_k=None` and expects all 28 scores back, then derives three separate
values from that one distribution:

- `surface_emotion` — argmax
- `core_emotion` — highest-scoring *negative* label
- `suppressed_emotion` — second highest

A softmax single-label model cannot supply that, which is exactly why the
earlier 6-class model was never promoted.

**Mode: `{"SMOKE" if smoke else "FULL"}`**
{"A 1% sample for 1 epoch. Proves data loading, label shape, loss, metrics and the hub push path before spending GPU quota." if smoke else "Full training run."}
"""
        ),
        code(
            f'''# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SMOKE_MODE = {smoke}

BASE_MODEL   = "roberta-base"
DATASET_ID   = "AmiruMallawarachchi/mindlens-go-emotions-cleaned"
TARGET_REPO  = "AmiruMallawarachchi/mindlens-emotion-classifier"

# Reporting threshold. Multi-label accuracy is close to meaningless, so the
# gate is MICRO-F1 at this threshold. 0.3 is the GoEmotions convention.
# It does not affect the app: the orchestrator RANKS the 28 scores rather
# than thresholding them.
THRESHOLD    = 0.3
GATE_MICRO_F1 = 0.80

EPOCHS       = 1 if SMOKE_MODE else 5
SAMPLE_FRAC  = 0.01 if SMOKE_MODE else 1.0
BATCH_SIZE   = 32
LR           = 2e-5
MAX_LENGTH   = 128
PUSH_TO_HUB  = not SMOKE_MODE   # a smoke run must never overwrite the model

print(f"mode={{'SMOKE' if SMOKE_MODE else 'FULL'}} epochs={{EPOCHS}} frac={{SAMPLE_FRAC}} push={{PUSH_TO_HUB}}")
'''
        ),
        code(
            """!pip install -q -U transformers datasets huggingface_hub scikit-learn accelerate"""
        ),
        code(
            """from huggingface_hub import login
from kaggle_secrets import UserSecretsClient

# Token comes from Kaggle Secrets — never hardcoded in the notebook.
user_secrets = UserSecretsClient()
login(token=user_secrets.get_secret("HF_TOKEN"))
print("Logged into HuggingFace")"""
        ),
        md(
            """## Labels

`id2label` must match `backend/app/core/emotion_labels.py` exactly, in
`LABEL_0 … LABEL_27` order. The orchestrator does
`label_map.get(raw_label, raw_label)`, so emitting canonical names here makes
that lookup a pass-through. A mismatch silently mislabels every emotion in
the product, so it is asserted rather than assumed."""
        ),
        code(
            f"""LABELS = {json.dumps(LABELS, indent=4)}

assert len(LABELS) == 28, "expected 28 labels"
assert LABELS[-1] == "neutral", "neutral must be the last label"

id2label = {{i: name for i, name in enumerate(LABELS)}}
label2id = {{name: i for i, name in enumerate(LABELS)}}
print(f"{{len(LABELS)}} labels — first: {{LABELS[0]}}, last: {{LABELS[-1]}}")"""
        ),
        md(
            """## Data

Pre-flight already confirmed this dataset is genuinely multi-label
(17.2% of train rows carry more than one label, all 28 ids present). The
assertion below keeps that true — if a future cleaning pass flattens it to
one label per row, this fails loudly here rather than silently training a
model that cannot do its job."""
        ),
        code(
            '''from datasets import load_dataset
import numpy as np

ds = load_dataset(DATASET_ID)
print(ds)

# Guard: the whole task depends on this staying multi-label.
train_lens = [len(x) for x in ds["train"]["labels"]]
multi_frac = float(np.mean([n > 1 for n in train_lens]))
print(f"multi-label rows: {multi_frac:.1%}  max labels/row: {max(train_lens)}")
assert multi_frac > 0.05, (
    f"dataset looks flattened to single-label ({multi_frac:.1%} multi-label) — "
    "multi-label training would be pointless. Check the cleaning notebook."
)

seen = {i for row in ds["train"]["labels"] for i in row}
assert seen <= set(range(28)), f"label ids outside 0..27: {sorted(seen - set(range(28)))}"
print(f"distinct label ids present: {len(seen)}/28")'''
        ),
        code(
            '''def to_multi_hot(batch):
    """Turn the list-of-ids into the float vector BCEWithLogits expects."""
    matrix = np.zeros((len(batch["labels"]), 28), dtype=np.float32)
    for row, ids in enumerate(batch["labels"]):
        for i in ids:
            matrix[row, i] = 1.0
    return {"labels": matrix.tolist()}


encoded = ds.map(to_multi_hot, batched=True)

if SAMPLE_FRAC < 1.0:
    for split in encoded:
        n = max(1, int(len(encoded[split]) * SAMPLE_FRAC))
        encoded[split] = encoded[split].shuffle(seed=42).select(range(n))
    print("SMOKE sample:", {s: len(encoded[s]) for s in encoded})

print("label vector length:", len(encoded["train"][0]["labels"]))
assert len(encoded["train"][0]["labels"]) == 28'''
        ),
        code(
            '''from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

def tokenize(batch):
    return tokenizer(batch["text"], truncation=True, max_length=MAX_LENGTH)

tokenized = encoded.map(tokenize, batched=True, remove_columns=["text"])
tokenized.set_format("torch")
print(tokenized)'''
        ),
        md(
            """## Model

`problem_type="multi_label_classification"` is what makes Trainer use
`BCEWithLogitsLoss` and sigmoid outputs instead of softmax + cross-entropy.
Getting this wrong produces a model that trains and evaluates without
complaint but cannot express two feelings at once."""
        ),
        code(
            '''from transformers import AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained(
    BASE_MODEL,
    num_labels=28,
    problem_type="multi_label_classification",
    id2label=id2label,
    label2id=label2id,
)
assert model.config.problem_type == "multi_label_classification"
assert model.config.num_labels == 28
print("head:", model.config.problem_type, model.config.num_labels)'''
        ),
        code(
            '''import torch
from sklearn.metrics import f1_score, precision_recall_fscore_support, roc_auc_score

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = sigmoid(logits)
    preds = (probs >= THRESHOLD).astype(int)
    return {
        "micro_f1": f1_score(labels, preds, average="micro", zero_division=0),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        # Threshold-free, so it stays comparable if THRESHOLD is retuned.
        "roc_auc_macro": roc_auc_score(labels, probs, average="macro"),
    }'''
        ),
        code(
            '''from transformers import Trainer, TrainingArguments, DataCollatorWithPadding

args = TrainingArguments(
    output_dir="./emotion-multilabel",
    learning_rate=LR,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    num_train_epochs=EPOCHS,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="micro_f1",
    greater_is_better=True,
    logging_steps=50,
    fp16=torch.cuda.is_available(),
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized["validation"],
    tokenizer=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer),
    compute_metrics=compute_metrics,
)

trainer.train()'''
        ),
        md("""## Held-out evaluation"""),
        code(
            '''import pandas as pd

pred = trainer.predict(tokenized["test"])
probs = sigmoid(pred.predictions)
preds = (probs >= THRESHOLD).astype(int)
gold = np.array(pred.label_ids)

micro = f1_score(gold, preds, average="micro", zero_division=0)
macro = f1_score(gold, preds, average="macro", zero_division=0)
print(f"MICRO-F1 (gated metric, threshold {THRESHOLD}): {micro:.4f}")
print(f"MACRO-F1: {macro:.4f}")

p, r, f, support = precision_recall_fscore_support(
    gold, preds, average=None, zero_division=0, labels=list(range(28))
)
per_label = pd.DataFrame({
    "label": LABELS,
    "precision": p.round(4),
    "recall": r.round(4),
    "f1": f.round(4),
    "support": support,
}).sort_values("f1", ascending=False)
per_label'''
        ),
        md(
            """## Baseline comparison

Proposal deliverable 1 explicitly asks for a baseline-vs-fine-tuned table.
The incumbent is the off-the-shelf `SamLowe/roberta-base-go_emotions` that
`config.py` currently points at.

Labels are matched **by name, not index** — the baseline's own `id2label`
ordering is not guaranteed to match ours, and aligning by position would
silently compare the wrong classes."""
        ),
        code(
            '''from transformers import pipeline as hf_pipeline

BASELINE_ID = "SamLowe/roberta-base-go_emotions"
baseline = hf_pipeline(
    "text-classification", model=BASELINE_ID, top_k=None,
    truncation=True, max_length=MAX_LENGTH,
    device=0 if torch.cuda.is_available() else -1,
)

test_texts = ds["test"]["text"][: len(gold)]
raw = baseline(test_texts, batch_size=64)

# Align by NAME. Anything the baseline does not emit stays 0.
base_probs = np.zeros_like(probs)
for row, scores in enumerate(raw):
    for item in scores:
        idx = label2id.get(item["label"])
        if idx is not None:
            base_probs[row, idx] = item["score"]

base_preds = (base_probs >= THRESHOLD).astype(int)
base_micro = f1_score(gold, base_preds, average="micro", zero_division=0)
base_macro = f1_score(gold, base_preds, average="macro", zero_division=0)

comparison = pd.DataFrame({
    "model": [f"baseline ({BASELINE_ID})", f"fine-tuned ({BASE_MODEL})"],
    "micro_f1": [round(base_micro, 4), round(micro, 4)],
    "macro_f1": [round(base_macro, 4), round(macro, 4)],
})
comparison'''
        ),
        code(
            '''import json, os, datetime

os.makedirs("/kaggle/working/reports", exist_ok=True)
report = {
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "mode": "smoke" if SMOKE_MODE else "full",
    "base_model": BASE_MODEL,
    "dataset": DATASET_ID,
    "threshold": THRESHOLD,
    "gated_metric": "micro_f1",
    "gate": GATE_MICRO_F1,
    "epochs": EPOCHS,
    "sample_fraction": SAMPLE_FRAC,
    "fine_tuned": {"micro_f1": float(micro), "macro_f1": float(macro)},
    "baseline": {
        "model": BASELINE_ID,
        "micro_f1": float(base_micro),
        "macro_f1": float(base_macro),
    },
    "per_label": per_label.to_dict(orient="records"),
    "note": (
        "micro_f1 is the gated metric; multi-label accuracy is not reported "
        "because it is close to meaningless on this task. THRESHOLD affects "
        "these figures but not the running app, which ranks the 28 scores."
    ),
}
with open("/kaggle/working/reports/emotion_classifier_eval.json", "w") as fh:
    json.dump(report, fh, indent=2)
print(json.dumps({k: report[k] for k in ("mode", "fine_tuned", "baseline")}, indent=2))'''
        ),
        md(
            """## Gate and publish

The retraining protocol gates on micro-F1 ≥ 0.80. A smoke run never
publishes — it exists to prove the plumbing, and its 1% scores are
meaningless. A full run that misses the gate does not ship either; the
failure gets documented rather than quietly released."""
        ),
        code(
            '''if SMOKE_MODE:
    print("SMOKE run complete — plumbing verified, nothing published.")
    print("Re-generate with --full and push again for the real run.")
elif micro >= GATE_MICRO_F1:
    trainer.model.push_to_hub(TARGET_REPO)
    tokenizer.push_to_hub(TARGET_REPO)
    print(f"PASSED gate ({micro:.4f} >= {GATE_MICRO_F1}) — pushed to {TARGET_REPO}")
else:
    print(f"FAILED gate: micro-F1 {micro:.4f} < {GATE_MICRO_F1}. Not published.")
    print("Document the gate failure per the retraining protocol.")'''
        ),
    ]

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="full run instead of smoke")
    opts = parser.parse_args()

    OUT.write_text(json.dumps(build(smoke=not opts.full), indent=1), encoding="utf-8")
    print(f"wrote {OUT} (mode={'FULL' if opts.full else 'SMOKE'})")
