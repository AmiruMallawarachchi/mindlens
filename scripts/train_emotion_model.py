# ============================================
# MindLens Emotion Model - Kaggle T4 Training
# ============================================

#!pip install -q transformers datasets accelerate huggingface_hub

from huggingface_hub import login
from kaggle_secrets import UserSecretsClient # type: ignore
user_secrets = UserSecretsClient()
hf_token = user_secrets.get_secret("HF_TOKEN")
login(token=hf_token)
print("Logged into HuggingFace")

import torch  # noqa: E402
import os  # noqa: E402
import numpy as np  # noqa: E402
from collections import Counter  # noqa: E402
from transformers import (  # noqa: E402
    AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments,
    Trainer, EarlyStoppingCallback, DataCollatorWithPadding
)
from datasets import load_dataset, concatenate_datasets  # noqa: E402
from sklearn.metrics import f1_score, accuracy_score, recall_score, precision_score  # noqa: E402, F401

BASE_MODEL = "roberta-base"
YOUR_HF_USERNAME = "AmiruMallawarachchi"
OUTPUT_DIR = "/kaggle/working/mindlens-emotion"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"CUDA: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")

# ============================================
# AUTO-DETECT DATASET COLUMNS
# ============================================
def inspect_dataset(name, ds_dict):
    """Print structure so we know what we're working with"""
    print(f"\n--- {name} ---")
    for split in ds_dict.keys():
        ds = ds_dict[split]
        print(f"  Split '{split}': {len(ds)} rows")
        print(f"  Columns: {ds.column_names}")
        if len(ds) > 0:
            print(f"  First example: {ds[0]}")
    return ds_dict

def find_column(columns, candidates):
    """Find first matching column from candidates list"""
    for c in candidates:
        if c in columns:
            return c
    return None

# ============================================
# LOAD & INSPECT
# ============================================
ds_go = inspect_dataset("go-emotions", load_dataset(f"{YOUR_HF_USERNAME}/mindlens-go-emotions-cleaned"))
ds_dair = inspect_dataset("dair-emotion", load_dataset(f"{YOUR_HF_USERNAME}/mindlens-dair-emotion-cleaned"))

# Use train splits
train_go = ds_go["train"] # type: ignore
train_dair = ds_dair["train"] # type: ignore

# Detect text column
text_col_go = find_column(train_go.column_names, ["text", "tweet", "sentence", "content", "body"]) # type: ignore
text_col_dair = find_column(train_dair.column_names, ["text", "tweet", "sentence", "content", "body"]) # type: ignore

# Detect label column
label_col_go = find_column(train_go.column_names, ["label", "labels", "emotion", "category", "class"]) # type: ignore
label_col_dair = find_column(train_dair.column_names, ["label", "labels", "emotion", "category", "class"]) # type: ignore

print(f"\nDetected columns:")  # noqa: F541
print(f"  go-emotions: text='{text_col_go}', label='{label_col_go}'")
print(f"  dair-emotion: text='{text_col_dair}', label='{label_col_dair}'")

assert text_col_go and label_col_go, "Could not detect go-emotions columns"
assert text_col_dair and label_col_dair, "Could not detect dair-emotion columns"

# ============================================
# NORMALIZE LABELS
# ============================================
# Check if go-emotions labels are multi-label (list) or single (int)
sample_label_go = train_go[0][label_col_go]
sample_label_dair = train_dair[0][label_col_dair]

print(f"\nSample label types: go={type(sample_label_go)}={sample_label_go}, dair={type(sample_label_dair)}={sample_label_dair}")

def normalize_label(example, text_key, label_key, label_map=None, is_multi=False):
    """Convert any label format to a single integer"""
    text = example[text_key]
    raw_label = example[label_key]
    
    if is_multi and isinstance(raw_label, list):
        # Multi-label: pick the first / highest index, or argmax if floats
        label = int(np.argmax(raw_label)) if all(isinstance(x, (int, float)) for x in raw_label) else int(raw_label[0])
    else:
        label = int(raw_label)
    
    if label_map:
        label = label_map.get(label, label)
    
    return {"text": text, "label": label}

# Determine if go-emotions is multi-label
is_go_multi = isinstance(sample_label_go, list) or (isinstance(sample_label_go, str) and sample_label_go.startswith("["))

# Get unique labels from both datasets to build unified mapping
go_labels = set()
for i in range(min(1000, len(train_go))):
    raw = train_go[i][label_col_go]
    if is_go_multi and isinstance(raw, list):
        go_labels.update([int(x) for x in raw] if all(isinstance(x, (int,float)) for x in raw) else [int(raw[0])])
    else:
        go_labels.add(int(raw))

dair_labels = set(int(train_dair[i][label_col_dair]) for i in range(min(1000, len(train_dair))))

print(f"  go-emotions unique labels (sample): {sorted(go_labels)}")
print(f"  dair-emotion unique labels (sample): {sorted(dair_labels)}")

# If label spaces overlap (e.g., both 0-5), we can concatenate directly
# If they differ, we need to remap. For now, assume they share the same space.
# If not, we'll remap dair to start after go-emotions max
if dair_labels.issubset(go_labels) or go_labels.issubset(dair_labels):
    # Compatible label spaces
    label_map_go = None
    label_map_dair = None
    print("Label spaces are compatible. Concatenating directly.")
else:
    # Remap dair labels to avoid collision
    max_go = max(go_labels)
    dair_to_unified = {old: max_go + 1 + i for i, old in enumerate(sorted(dair_labels))}
    label_map_dair = dair_to_unified
    label_map_go = None
    print(f"Label spaces differ. Remapping dair: {dair_to_unified}")

# Apply normalization
train_go = train_go.map( # type: ignore
    lambda ex: normalize_label(ex, text_col_go, label_col_go, label_map_go, is_go_multi),
    remove_columns=train_go.column_names # type: ignore
)
train_dair = train_dair.map( # type: ignore
    lambda ex: normalize_label(ex, text_col_dair, label_col_dair, label_map_dair, False),
    remove_columns=train_dair.column_names # type: ignore
)

# Combine
train_ds = concatenate_datasets([train_go, train_dair]).shuffle(seed=42)

# Validation
if "validation" in ds_go:
    val_go = ds_go["validation"] # type: ignore
    val_go = val_go.map( # type: ignore
        lambda ex: normalize_label(ex, text_col_go, label_col_go, label_map_go, is_go_multi),
        remove_columns=val_go.column_names # type: ignore
    )
    val_ds = val_go
else:
    split = train_ds.train_test_split(test_size=0.1, seed=42)
    train_ds = split["train"]
    val_ds = split["test"]

print(f"\nCombined: Train={len(train_ds)}, Val={len(val_ds)}")
all_labels = [train_ds[i]["label"] for i in range(min(1000, len(train_ds)))]
num_labels = max(all_labels) + 1
print(f"Num classes: {num_labels}")
print(f"Label distribution: {Counter(all_labels)}")

# ============================================
# TOKENIZE
# ============================================
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=num_labels)

def preprocess(examples):
    tokens = tokenizer(examples["text"], truncation=True, padding=False, max_length=256)
    tokens["labels"] = examples["label"]
    return tokens

train_ds = train_ds.map(preprocess, batched=True)
val_ds = val_ds.map(preprocess, batched=True)

cols_to_remove = [c for c in train_ds.column_names if c not in ["input_ids", "attention_mask", "labels"]]
train_ds = train_ds.remove_columns(cols_to_remove)
val_ds = val_ds.remove_columns(cols_to_remove)

# ============================================
# TRAIN
# ============================================
def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    preds = np.argmax(predictions, axis=1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro", zero_division=0),
        "f1_weighted": f1_score(labels, preds, average="weighted", zero_division=0),
        "recall": recall_score(labels, preds, average="macro", zero_division=0),
    }

args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    num_train_epochs=4,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",
    greater_is_better=True,
    logging_steps=500,
    fp16=True,
    report_to="none",
    seed=42
)

trainer = Trainer(
    model=model, args=args,
    train_dataset=train_ds, eval_dataset=val_ds,
    processing_class=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer),
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

print("\n>>> STARTING TRAINING <<<\n")
trainer.train()

metrics = trainer.evaluate()
print(f"\n{'='*60}")
print(f"F1 MACRO:    {metrics['eval_f1_macro']:.4f}")
print(f"F1 WEIGHTED: {metrics['eval_f1_weighted']:.4f}")
print(f"ACCURACY:     {metrics['eval_accuracy']:.4f}")
print(f"RECALL:       {metrics['eval_recall']:.4f}")
print(f"{'='*60}\n")

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

from huggingface_hub import HfApi  # noqa: E402
api = HfApi()
repo_id = f"{YOUR_HF_USERNAME}/mindlens-emotion"
api.create_repo(repo_id=repo_id, exist_ok=True)
api.upload_folder(folder_path=OUTPUT_DIR, repo_id=repo_id)
print(f"\n>>> UPLOADED: https://huggingface.co/{repo_id}")