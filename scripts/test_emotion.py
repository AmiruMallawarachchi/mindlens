#!/usr/bin/env python3
"""
Quick local test for the pre-trained go-emotions model.
Run this to verify your emotion pipeline works before moving to MH.
"""
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

MODEL_ID = "SamLowe/roberta-base-go_emotions"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)

device = 0 if torch.cuda.is_available() else -1
print(f"Device: {'GPU' if device == 0 else 'CPU'}")

# Create pipeline with sigmoid for multi-label
emotion_pipe = pipeline(
    "text-classification",
    model=model,
    tokenizer=tokenizer,
    device=device,
    return_all_scores=True,
    function_to_apply="sigmoid"
)

# Test inputs
test_texts = [
    "I feel so happy today, everything is going great!",
    "I'm really anxious about my exam tomorrow and can't sleep",
    "I lost my job and I don't know how to go on anymore",
    "I'm angry and frustrated with how things turned out",
    "I miss my friend so much, it hurts every day"
]

print("\n" + "="*70)
for text in test_texts:
    result = emotion_pipe(text)[0] # type: ignore
    scores = {r["label"]: round(r["score"], 3) for r in result} # type: ignore
    
    # Sort by score descending
    top3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    
    print(f"\nText: {text}")
    print(f"  Top 3 emotions: {top3}")
    
    # Detect valence
    negative = ["sadness", "grief", "anger", "fear", "disgust", "annoyance", 
                "disappointment", "remorse", "embarrassment", "nervousness"]
    has_negative = any(scores.get(e, 0) > 0.3 for e in negative)
    valence = "negative" if has_negative else "positive" if scores.get("joy", 0) > 0.3 else "neutral"
    print(f"  Valence: {valence}")

print("\n" + "="*70)
print("Test complete. If you see 28 emotion scores per text, you're good.")