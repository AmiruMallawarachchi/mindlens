# ============================================
# MindLens Crisis Model - Kaggle T4 Training
# ============================================

#!pip install -q transformers datasets accelerate huggingface_hub

from huggingface_hub import login
from kaggle_secrets import UserSecretsClient  # type: ignore

user_secrets = UserSecretsClient()
hf_token = user_secrets.get_secret("HF_TOKEN")
login(token=hf_token)
print("Logged into HuggingFace")

import os  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from datasets import load_dataset  # noqa: E402
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score  # noqa: E402
from transformers import (  # noqa: E402
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

BASE_MODEL = "distilbert-base-uncased"
YOUR_HF_USERNAME = "AmiruMallawarachchi"

# v3 dataset: raw text (not lemmatized), hard negatives, short turns in BOTH
# classes. v1 scored 0.82 on "I'm scared it will not be good enough" against
# 0.88 for "I want to kill myself". v2 fixed that but only for the safe
# class — its crisis class was still 100% long-form Reddit posts (median 69
# words), so it learned "short == not crisis" and scored "I want to kill
# myself" at 0.367, missing 5/5 blunt crisis probes. v3 adds the mirror
# synthetic set on the crisis side. See scripts/build_crisis_dataset.py.
DATASET_NAME = f"{YOUR_HF_USERNAME}/mindlens-crisis-cleaned-v3"

# Publishes alongside the live model rather than over it. Swap
# config.py's crisis_model_id only after the probes below look right —
# never overwrite a shipped crisis classifier in place.
TARGET_REPO = f"{YOUR_HF_USERNAME}/mindlens-crisis-v3"

OUTPUT_DIR = "/kaggle/working/mindlens-crisis-v2"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Messages that must NOT be flagged. The first two are the observed
# production false positives; the model is not fixed until these are low.
PROBE_SAFE = [
    "so i need a help okay",
    "It is mostly that I am scared it will not be good enough.",
    "I have been really anxious about my final year project.",
    "I'm worried I will disappoint my parents.",
    "I feel like a failure honestly.",
    "I had a rough day at work today.",
]

# Messages that MUST be flagged. A regression here is far worse than a
# regression above, so these are checked at the same time and reported
# together — never tune one list without looking at the other.
PROBE_CRISIS = [
    "I want to kill myself",
    "I am going to end it all tonight",
    "I do not want to be alive anymore",
    "There is no point in living",
    "I have been thinking about suicide",
]

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    preds = np.argmax(predictions, axis=1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, zero_division=0),
        "recall": recall_score(labels, preds, zero_division=0),
        "precision": precision_score(labels, preds, zero_division=0)
    }

print(f"\nLoading dataset: {DATASET_NAME}")
ds = load_dataset(DATASET_NAME)
train_ds = ds["train"] # type: ignore
val_ds = ds.get("validation") or ds.get("test") or train_ds.select(range(5000)) # type: ignore

print(f"Train: {len(train_ds)}, Val: {len(val_ds)}")

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
sample_labels = [train_ds[i]["label"] for i in range(min(100, len(train_ds)))]
num_labels = max(sample_labels) + 1
print(f"Detected num_labels: {num_labels}")

model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=num_labels)

def preprocess(examples):
    text_col = "text" if "text" in examples else "tweet"
    label_col = "label" if "label" in examples else "labels"
    tokens = tokenizer(examples[text_col], truncation=True, padding=False, max_length=256)
    tokens["labels"] = examples[label_col]
    return tokens

train_ds = train_ds.map(preprocess, batched=True) # type: ignore
val_ds = val_ds.map(preprocess, batched=True)

columns_to_remove = [c for c in train_ds.column_names if c not in ["input_ids", "attention_mask", "labels"]]
train_ds = train_ds.remove_columns(columns_to_remove)
val_ds = val_ds.remove_columns(columns_to_remove)

args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    learning_rate=3e-5,
    per_device_train_batch_size=32,
    per_device_eval_batch_size=64,
    num_train_epochs=3,
    weight_decay=0.01,
    load_best_model_at_end=True,
    # f1, not recall. Selecting on recall alone rewards the checkpoint that
    # flags the most text, which is part of how a model that calls "I'm
    # scared it won't be good enough" a crisis got picked as best. Recall is
    # still computed and printed every epoch — it just no longer chooses the
    # checkpoint on its own.
    metric_for_best_model="f1",
    greater_is_better=True,
    logging_steps=500,
    fp16=True,
    report_to="none",
    seed=42
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    processing_class=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer),
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

print("\n>>> STARTING TRAINING <<<\n")
trainer.train()

metrics = trainer.evaluate()
print(f"\n{'='*60}")
print(f"FINAL RECALL: {metrics['eval_recall']:.4f} (TARGET: >0.90)")
print(f"FINAL F1:     {metrics['eval_f1']:.4f}")
print(f"FINAL ACC:    {metrics['eval_accuracy']:.4f}")
print(f"{'='*60}\n")

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

# ---------------------------------------------------------------------------
# Probes: the specific failures this retrain exists to fix.
#
# Aggregate F1 hid the original bug completely — v1 scored well on a test set
# drawn from the same lemmatized Reddit distribution it was trained on, while
# failing on the short, sincere messages the product actually receives. These
# probes are the acceptance check; the headline metrics are not.
# ---------------------------------------------------------------------------
import torch.nn.functional as F  # noqa: E402

model.eval()
device = next(model.parameters()).device


def crisis_prob(text):
    enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=256).to(device)
    with torch.no_grad():
        return F.softmax(model(**enc).logits, dim=-1)[0][1].item()


print(f"\n{'='*68}")
print("PROBES — must stay LOW (these were the production false positives)")
print(f"{'='*68}")
safe_scores = []
for t in PROBE_SAFE:
    p = crisis_prob(t)
    safe_scores.append(p)
    print(f"  {p:.3f}  {'FLAGGED' if p > 0.45 else 'ok     '}  {t[:58]}")

print(f"\n{'='*68}")
print("PROBES — must stay HIGH (missing one of these is the worse failure)")
print(f"{'='*68}")
crisis_scores = []
for t in PROBE_CRISIS:
    p = crisis_prob(t)
    crisis_scores.append(p)
    print(f"  {p:.3f}  {'ok     ' if p > 0.45 else 'MISSED '}  {t[:58]}")

print(f"\n{'='*68}")
print("THRESHOLD SWEEP (probe sets)")
print(f"{'='*68}")
print(f"{'thresh':>8} {'false pos':>12} {'crisis caught':>16}")
for th in (0.45, 0.5, 0.6, 0.7, 0.8, 0.9):
    fp = sum(1 for s in safe_scores if s > th)
    tp = sum(1 for s in crisis_scores if s > th)
    print(f"{th:>8} {fp:>7}/{len(safe_scores):<4} {tp:>10}/{len(crisis_scores):<5}")

margin = min(crisis_scores) - max(safe_scores)
print(f"\nSeparation margin: {margin:+.3f}")
print("  v1 margin was +0.06 (0.88 crisis vs 0.82 benign) — too thin for any")
print("  threshold to split. A comfortably positive margin here is the goal.")
if margin <= 0:
    print("  *** MARGIN NOT POSITIVE — do not ship this checkpoint. ***")

from huggingface_hub import HfApi  # noqa: E402

api = HfApi()
api.create_repo(repo_id=TARGET_REPO, exist_ok=True, private=True)
api.upload_folder(folder_path=OUTPUT_DIR, repo_id=TARGET_REPO)
print(f"\n>>> UPLOADED: https://huggingface.co/{TARGET_REPO}")
print(">>> Live model untouched. Point config.py at this only after the")
print(">>> probes above look right.")
