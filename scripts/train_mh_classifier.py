# ============================================
# MindLens MH Classifier - Kaggle T4 Training
# ============================================

# !pip install -q transformers datasets accelerate huggingface_hub

from huggingface_hub import login
from kaggle_secrets import UserSecretsClient  # type: ignore
user_secrets = UserSecretsClient()
hf_token = user_secrets.get_secret("HF_TOKEN")
login(token=hf_token)
print("Logged into HuggingFace")

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import numpy as np  # noqa: E402
import json  # noqa: E402
from transformers import (  # noqa: E402
    AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments,
    Trainer, DataCollatorWithPadding
)
from datasets import load_dataset  # noqa: E402
from sklearn.metrics import f1_score, roc_auc_score  # noqa: E402

BASE_MODEL = "mental/mental-bert-base-uncased"
YOUR_HF_USERNAME = "AmiruMallawarachchi"
DATASET_NAME = f"{YOUR_HF_USERNAME}/mindlens-ourafla-mh-cleaned"
OUTPUT_DIR = "/kaggle/working/mindlens-mh-classifier"
import os  # noqa: E402
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"CUDA: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")

# ============================================
# LOAD & INSPECT
# ============================================
ds = load_dataset(DATASET_NAME)
train_ds = ds["train"] # type: ignore
val_ds = ds.get("validation") or ds.get("test") or train_ds.select(range(5000)) # type: ignore

print(f"Train: {len(train_ds)}, Val: {len(val_ds)}")
print(f"Columns: {train_ds.column_names}") # type: ignore
sample = train_ds[0]
print(f"First example:\n{sample}")

# ============================================
# AUTO-DETECT & FLATTEN LABELS
# ============================================
def extract_labels(example):
    """Extract flat list of 5 floats from any label format"""
    if "condition_vector" in example:
        vec = example["condition_vector"]
        # Handle nested: [[0.0, 1.0, 0.0, 0.0, 0.0]] or flat: [0.0, 1.0, 0.0, 0.0, 0.0]
        if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], list):
            vec = vec[0]  # Unwrap nested list
        return [float(x) for x in vec]
    
    elif "labels" in example and isinstance(example["labels"], list):
        return [float(x) for x in example["labels"]]
    
    elif all(c in example for c in ["depression", "anxiety", "stress", "burnout", "ptsd"]):
        return [float(example[c]) for c in ["depression", "anxiety", "stress", "burnout", "ptsd"]]
    
    else:
        raise ValueError(f"Cannot extract labels from: {example}")

# Test extraction
test_labels = extract_labels(sample)
NUM_LABELS = len(test_labels)
LABEL_NAMES = ["depression", "anxiety", "stress", "burnout", "ptsd"]
print(f"Extracted labels: {test_labels}")
print(f"Num labels: {NUM_LABELS}")

def get_labels(examples):
    """Batch version for dataset.map()"""
    all_labels = []
    for i in range(len(examples["text"])):
        # Reconstruct single example
        ex = {k: examples[k][i] for k in examples.keys()}
        all_labels.append(extract_labels(ex))
    return {"labels": all_labels}

# ============================================
# TOKENIZE
# ============================================
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForSequenceClassification.from_pretrained(
    BASE_MODEL, 
    num_labels=NUM_LABELS, 
    problem_type="multi_label_classification"
)

def preprocess(examples):
    tokens = tokenizer(examples["text"], truncation=True, padding=False, max_length=256)
    labels = get_labels(examples)
    tokens["labels"] = labels["labels"]
    return tokens

train_ds = train_ds.map(preprocess, batched=True) # type: ignore
val_ds = val_ds.map(preprocess, batched=True)

cols_to_remove = [c for c in train_ds.column_names if c not in ["input_ids", "attention_mask", "labels"]]
train_ds = train_ds.remove_columns(cols_to_remove)
val_ds = val_ds.remove_columns(cols_to_remove)

# ============================================
# MULTI-LABEL TRAINER
# ============================================
class MultiLabelTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        
        loss_fct = nn.BCEWithLogitsLoss()
        if not isinstance(labels, torch.Tensor):
            labels = torch.tensor(labels, dtype=torch.float32, device=logits.device)
        else:
            labels = labels.to(logits.device).float()
        
        loss = loss_fct(logits, labels)
        return (loss, outputs) if return_outputs else loss

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    probs = 1 / (1 + np.exp(-predictions))
    preds = (probs > 0.5).astype(int)
    
    f1_macro = f1_score(labels, preds, average="macro", zero_division=0)
    f1_micro = f1_score(labels, preds, average="micro", zero_division=0)
    
    aucs = []
    for i in range(labels.shape[1]):
        if len(set(labels[:, i])) > 1:
            try:
                aucs.append(roc_auc_score(labels[:, i], probs[:, i]))
            except:  # noqa: E722
                pass
    avg_auc = np.mean(aucs) if aucs else 0.0
    
    return {
        "f1_macro": f1_macro,
        "f1_micro": f1_micro,
        "avg_auc": avg_auc,
    }

# ============================================
# TRAIN
# ============================================
args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    num_train_epochs=3,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",
    greater_is_better=True,
    logging_steps=500,
    fp16=True,
    report_to="none",
    seed=42
)

trainer = MultiLabelTrainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    processing_class=tokenizer,
    data_collator=DataCollatorWithPadding(tokenizer),
    compute_metrics=compute_metrics
)

print("\n>>> STARTING MH CLASSIFIER TRAINING <<<\n")
trainer.train()

metrics = trainer.evaluate()
print(f"\n{'='*60}")
print(f"F1 MACRO:  {metrics['eval_f1_macro']:.4f}  (TARGET: >0.70)")
print(f"F1 MICRO:  {metrics['eval_f1_micro']:.4f}")
print(f"AVG AUC:   {metrics['eval_avg_auc']:.4f}")
print(f"{'='*60}\n")

# ============================================
# SAVE & UPLOAD
# ============================================
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

with open(f"{OUTPUT_DIR}/label_config.json", "w") as f:
    json.dump({"label_names": LABEL_NAMES, "num_labels": NUM_LABELS}, f)

from huggingface_hub import HfApi  # noqa: E402
api = HfApi()
repo_id = f"{YOUR_HF_USERNAME}/mindlens-mh-classifier"
api.create_repo(repo_id=repo_id, exist_ok=True)
api.upload_folder(folder_path=OUTPUT_DIR, repo_id=repo_id)
print(f"\n>>> UPLOADED: https://huggingface.co/{repo_id}")