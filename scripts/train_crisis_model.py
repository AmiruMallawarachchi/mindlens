#!/usr/bin/env python3
"""
Train MindLens Crisis Safety Classifier
"""

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback
)
from datasets import load_dataset, Dataset
from sklearn.metrics import f1_score, accuracy_score, recall_score, precision_score
import numpy as np
import os

BASE_MODEL = "distilbert-base-uncased"
OUTPUT_DIR = "data/models/mindlens-crisis"
YOUR_HF_USERNAME = "AmiruMallawarachchi"
DATASET_NAME = f"{YOUR_HF_USERNAME}/mindlens-crisis-cleaned"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    preds = np.argmax(predictions, axis=1)
    
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, zero_division=0),
        "recall": recall_score(labels, preds, zero_division=0),
        "precision": precision_score(labels, preds, zero_division=0)
    }

def main():
    print("=" * 60)
    print("MindLens Crisis Safety Model Training")
    print("=" * 60)
    
    print(f"\nLoading dataset: {DATASET_NAME}")
    ds = load_dataset(DATASET_NAME)
    
    # FIXED: Explicitly cast to Dataset type
    train_ds: Dataset = ds["train"]
    val_ds: Dataset = ds.get("validation") or ds.get("test") or train_ds.select(range(1000))
    
    print(f"Train: {len(train_ds)}, Val: {len(val_ds)}")
    print(f"Columns: {train_ds.column_names}")
    print(f"First example: {train_ds[0]}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    
    # Determine num_labels
    sample_labels = [train_ds[i]["label"] for i in range(min(100, len(train_ds)))]
    num_labels = max(sample_labels) + 1
    print(f"\nDetected num_labels: {num_labels}")
    
    # Load model
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=num_labels
    )
    
    # Preprocess
    def preprocess(examples: dict):
        text_col = "text" if "text" in examples else "tweet"
        label_col = "label" if "label" in examples else "labels"
        
        tokens = tokenizer(
            examples[text_col],
            truncation=True,
            padding=False,
            max_length=256
        )
        tokens["labels"] = examples[label_col]
        return tokens
    
    # FIXED: Remove columns properly
    train_ds = train_ds.map(preprocess, batched=True)
    val_ds = val_ds.map(preprocess, batched=True)
    
    # Remove original columns, keep only model inputs
    columns_to_remove = [c for c in train_ds.column_names if c not in ["input_ids", "attention_mask", "labels"]]
    train_ds = train_ds.remove_columns(columns_to_remove)
    val_ds = val_ds.remove_columns(columns_to_remove)
    
    # Training args
    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=3e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=5,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="recall",
        greater_is_better=True,
        logging_steps=100,
        fp16=torch.cuda.is_available(),
        report_to="none",
        save_total_limit=2,
    )
    
    from transformers import DataCollatorWithPadding
    collator = DataCollatorWithPadding(tokenizer)
    
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )
    
    print("\nStarting training...")
    trainer.train()
    
    print("\n" + "=" * 60)
    print("Final Evaluation")
    print("=" * 60)
    metrics = trainer.evaluate()
    print(f"Accuracy:  {metrics['eval_accuracy']:.4f}")
    print(f"Recall:    {metrics['eval_recall']:.4f}  (TARGET: >0.90)")
    print(f"Precision: {metrics['eval_precision']:.4f}")
    print(f"F1:        {metrics['eval_f1']:.4f}")
    
    if metrics['eval_recall'] < 0.90:
        print("\nWARNING: Recall below 90%!")
    else:
        print("\n✓ Safety threshold met.")
    
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print("\nUploading to HuggingFace Hub...")
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(repo_id=f"{YOUR_HF_USERNAME}/mindlens-crisis", exist_ok=True)
    api.upload_folder(
        folder_path=OUTPUT_DIR,
        repo_id=f"{YOUR_HF_USERNAME}/mindlens-crisis"
    )
    print(f"✓ Uploaded: {YOUR_HF_USERNAME}/mindlens-crisis")
    
    print("\n" + "=" * 60)
    print("Training Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()