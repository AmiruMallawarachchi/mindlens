# ============================================
# MindLens Crisis Model - Kaggle T4 Training
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
from transformers import (  # noqa: E402
    AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments,
    Trainer, EarlyStoppingCallback, DataCollatorWithPadding
)
from datasets import load_dataset  # noqa: E402
from sklearn.metrics import f1_score, accuracy_score, recall_score, precision_score  # noqa: E402

BASE_MODEL = "distilbert-base-uncased"
YOUR_HF_USERNAME = "AmiruMallawarachchi"
DATASET_NAME = f"{YOUR_HF_USERNAME}/mindlens-crisis-cleaned"
OUTPUT_DIR = "/kaggle/working/mindlens-crisis"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    metric_for_best_model="recall",
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

from huggingface_hub import HfApi  # noqa: E402
api = HfApi()
repo_id = f"{YOUR_HF_USERNAME}/mindlens-crisis"
api.create_repo(repo_id=repo_id, exist_ok=True)
api.upload_folder(folder_path=OUTPUT_DIR, repo_id=repo_id)
print(f"\n>>> UPLOADED: https://huggingface.co/{repo_id}")