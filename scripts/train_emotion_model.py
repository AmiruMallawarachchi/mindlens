#!/usr/bin/env python3
"""
Train the MindLens Emotion Classifier
Base: cardiffnlp/twitter-roberta-base-emotion
Fine-tuned on GoEmotions + DAIR-AI Emotion
"""

import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    TrainingArguments, 
    Trainer,
    DataCollatorWithPadding
)
from datasets import load_dataset, concatenate_datasets
from sklearn.metrics import f1_score, accuracy_score
import numpy as np
import os

# Configuration
MODEL_NAME = "cardiffnlp/twitter-roberta-base-emotion"
OUTPUT_DIR = "data/models/mindlens-emotion"
MAX_LENGTH = 128
BATCH_SIZE = 8  # Reduce to 4 if you have < 8GB VRAM
GRADIENT_ACCUMULATION = 2
EPOCHS = 3
LEARNING_RATE = 2e-5

# Create output dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1_macro": f1_score(labels, predictions, average="macro"),
        "f1_weighted": f1_score(labels, predictions, average="weighted")
    }

def main():
    print("Loading datasets...")
    
    # Primary dataset: GoEmotions (simplified to 28 classes)
    # Note: GoEmotions has multi-label, we simplify to single-label for this demo
    goemotions = load_dataset("go_emotions", "simplified")
    
    # For this demo, we'll use a smaller subset to fit on RTX 2050 4GB
    # In production, use the full dataset
    train_dataset = goemotions["train"].select(range(5000))  # Use 5000 for demo
    val_dataset = goemotions["validation"].select(range(1000))
    
    print(f"Train samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")
    
    # Load tokenizer and model
    print(f"Loading model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=28,  # GoEmotions has 27 emotions + 1 neutral
        ignore_mismatched_sizes=True  # Resize classification head
    )
    
    # Preprocessing
    def preprocess_function(examples):
        return tokenizer(
            examples["text"], 
            truncation=True, 
            padding=False, 
            max_length=MAX_LENGTH
        )
    
    train_dataset = train_dataset.map(preprocess_function, batched=True)
    val_dataset = val_dataset.map(preprocess_function, batched=True)
    
    # Format for PyTorch
    train_dataset = train_dataset.remove_columns(["text", "id"])
    val_dataset = val_dataset.remove_columns(["text", "id"])
    
    # Rename labels column if needed
    if "labels" not in train_dataset.column_names:
        train_dataset = train_dataset.rename_column("label", "labels")
        val_dataset = val_dataset.rename_column("label", "labels")
    
    train_dataset.set_format("torch")
    val_dataset.set_format("torch")
    
    # Training arguments (optimized for 4GB GPU)
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        logging_dir=f"{OUTPUT_DIR}/logs",
        logging_steps=50,
        fp16=torch.cuda.is_available(),  # Mixed precision for speed
        optim="adamw_torch",
        report_to="none"  # No W&B for now
    )
    
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics
    )
    
    print("Starting training...")
    trainer.train()
    
    # Save
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    # Final evaluation
    print("\nFinal Evaluation:")
    metrics = trainer.evaluate()
    print(metrics)
    
    print(f"\nModel saved to: {OUTPUT_DIR}")
    print("To push to HuggingFace Hub:")
    print(f"  huggingface-cli upload {OUTPUT_DIR} your-username/mindlens-emotion")

if __name__ == "__main__":
    main()