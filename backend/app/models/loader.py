"""
Load fine-tuned models from HuggingFace Hub
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from typing import Dict, Any, Optional

YOUR_HF_USERNAME = "AmiruMallawarachchi"

class ModelManager:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"ModelManager using device: {self.device}")
    
    def load_crisis(self):
        print("Loading crisis model...")
        model_id = f"{YOUR_HF_USERNAME}/mindlens-crisis"
        
        try:
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
        except Exception as e:
            print(f"✗ Failed to load crisis model: {e}")
            raise RuntimeError("Crisis model is required for safety.")
    
    def load_emotion(self):
        print("Loading emotion model...")
        model_id = f"{YOUR_HF_USERNAME}/mindlens-emotion"
        
        try:
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
                    return_all_scores=True
                )
            }
            print("✓ Emotion model loaded")
        except Exception as e:
            print(f"⚠ Emotion model not available: {e}")
    
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
            print(f"⚠ MH model not available: {e}")
    
    def load_all(self):
        self.load_crisis()
        self.load_emotion()
        self.load_mh()
        print(f"\nAll models loaded: {list(self.models.keys())}")
    
    async def predict_crisis(self, text: str) -> Dict[str, Any]:
        if "crisis" not in self.models:
            return {"is_crisis": False, "probability": 0.0, "error": "Model not loaded"}
        
        result = self.models["crisis"]["pipeline"](text)[0]
        scores = {r["label"]: r["score"] for r in result}
        
        # FIXED: Use list() and key function properly
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
            return {"core": "neutral", "surface": "neutral", "severity": 0.5}
        
        result = self.models["emotion"]["pipeline"](text)[0]
        scores = {r["label"]: r["score"] for r in result}
        top = max(scores.keys(), key=lambda k: scores[k]) if scores else "neutral"
        
        return {
            "core_emotion": top,
            "surface_emotion": top,
            "severity": scores.get(top, 0.5),
            "valence": "negative" if scores.get(top, 0.5) > 0.5 else "neutral",
            "all_scores": scores
        }
    
    async def predict_mh(self, text: str) -> Dict[str, Any]:
        if "mh" not in self.models:
            return {"conditions": {}, "dominant": "none"}
        
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
        
        # FIXED: Use max with key properly
        dominant = max(conditions.keys(), key=lambda k: conditions[k]) if conditions else "none"
        
        return {
            "conditions": conditions,
            "dominant_condition": dominant,
            "multi_label": [k for k, v in conditions.items() if v > 0.5]
        }

model_manager = ModelManager()