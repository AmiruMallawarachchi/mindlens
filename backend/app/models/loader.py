"""
Load fine-tuned models from HuggingFace Hub
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from typing import Dict, Any

YOUR_HF_USERNAME = "AmiruMallawarachchi"

class ModelManager:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"ModelManager using device: {self.device}")
    
    def load_crisis(self):
        print("Loading crisis model...")
        model_id = f"{YOUR_HF_USERNAME}/mindlens-crisis"
        
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSequenceClassification.from_pretrained(model_id).to(self.device)
        
        self.models["crisis"] = {
            "tokenizer": tokenizer,
            "model": model,
            "pipeline": pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                device=0 if self.device == "cuda" else -1,
                return_all_scores=True
            )
        }
        print("✓ Crisis model loaded")
    
    def load_emotion(self):
        print("Loading emotion model...")
        model_id = "SamLowe/roberta-base-go_emotions"
        
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSequenceClassification.from_pretrained(model_id).to(self.device)
        
        self.models["emotion"] = {
            "tokenizer": tokenizer,
            "model": model,
            "pipeline": pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                device=0 if self.device == "cuda" else -1,
                top_k=None,  # Returns all 28 scores
                function_to_apply="sigmoid"
            )
        }
        print("✓ Emotion model loaded")
    
    def load_mh(self):
        print("Loading MH classifier...")
        model_id = f"{YOUR_HF_USERNAME}/mindlens-mh-classifier"
        
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSequenceClassification.from_pretrained(model_id).to(self.device)
            
            self.models["mh"] = {
                "tokenizer": tokenizer,
                "model": model
            }
            print("✓ MH model loaded")
        except Exception as e:
            print(f"⚠ MH model not available yet: {e}")
            self.models["mh"] = None
    
    def load_all(self):
        self.load_crisis()
        self.load_emotion()
        self.load_mh()
        print(f"\nAll models loaded: {[k for k, v in self.models.items() if v is not None]}")
    
    async def predict_crisis(self, text: str) -> Dict[str, Any]:
        if "crisis" not in self.models:
            return {"is_crisis": False, "probability": 0.0, "error": "Model not loaded"}
        
        result = self.models["crisis"]["pipeline"](text)[0]
        scores = {r["label"]: r["score"] for r in result}
        crisis_label = max(scores.keys(), key=lambda k: scores[k]) if scores else "0"
        crisis_prob = scores.get(crisis_label, 0.0)
        
        return {
            "is_crisis": crisis_prob >= 0.45,
            "probability": crisis_prob,
            "severity_score": crisis_prob,
            "crisis_type": "suicidal_ideation" if crisis_prob > 0.7 else "crisis_state" if crisis_prob > 0.45 else "none",
            "all_scores": scores
        }
    
    async def predict_emotion(self, text: str) -> Dict[str, Any]:
        if "emotion" not in self.models:
            return {"core_emotion": "neutral", "surface_emotion": "neutral", "suppressed_emotion": None, "severity": 0.5, "valence": "neutral", "all_scores": {}}
        
        result = self.models["emotion"]["pipeline"](text)[0]
        scores = {r["label"]: r["score"] for r in result}
        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = sorted_emotions[0][0] if sorted_emotions else "neutral"
        
        negative_emotions = {"sadness", "grief", "anger", "fear", "disgust", "annoyance", 
                             "disappointment", "remorse", "embarrassment", "nervousness"}
        positive_emotions = {"joy", "admiration", "excitement", "love", "gratitude", "relief", "pride", "optimism"}
        
        negative_scores = {k: v for k, v in scores.items() if k in negative_emotions}
        core = max(negative_scores.keys(), key=lambda k: negative_scores[k]) if negative_scores else top
        
        suppressed = sorted_emotions[1][0] if len(sorted_emotions) > 1 and sorted_emotions[1][0] != top else None
        
        has_positive = any(scores.get(e, 0) > 0.3 for e in positive_emotions)
        has_negative = any(scores.get(e, 0) > 0.3 for e in negative_emotions)
        valence = "negative" if has_negative and not has_positive else "positive" if has_positive and not has_negative else "neutral"
        severity = max(negative_scores.values()) if negative_scores else scores.get(top, 0.5)
        
        return {
            "surface_emotion": top,
            "core_emotion": core,
            "suppressed_emotion": suppressed,
            "severity": severity,
            "valence": valence,
            "all_scores": scores
        }
    
    async def predict_mh(self, text: str) -> Dict[str, Any]:
        if "mh" not in self.models or self.models["mh"] is None:
            return {
                "conditions": {"depression": 0.0, "anxiety": 0.0, "stress": 0.0, "burnout": 0.0, "ptsd": 0.0},
                "dominant_condition": "none",
                "multi_label": []
            }
        
        model_data = self.models["mh"]
        tokenizer = model_data["tokenizer"]
        model = model_data["model"]
        
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256).to(self.device)
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        probs = torch.sigmoid(outputs.logits).cpu().numpy()[0]
        
        conditions = {
            "depression": float(probs[0]),
            "anxiety": float(probs[1]),
            "stress": float(probs[2]),
            "burnout": float(probs[3]),
            "ptsd": float(probs[4])
        }
        
        dominant = max(conditions.keys(), key=lambda k: conditions[k]) if conditions else "none"
        
        return {
            "conditions": conditions,
            "dominant_condition": dominant,
            "multi_label": [k for k, v in conditions.items() if v > 0.5]
        }

model_manager = ModelManager()