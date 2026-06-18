import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

CRISIS_LABELS = {
    0: "non_crisis",
    1: "suicidal_ideation",
    2: "self_harm",
    3: "hopelessness",
    4: "violence_risk",
}

class CrisisClassifier:
    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()

    def predict(self, text: str):
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True)

        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.softmax(logits, dim=1)

        confidence, pred = torch.max(probs, dim=1)

        label_id = int(pred.item())
        return {
            "crisis_type": CRISIS_LABELS.get(label_id, "unknown"),
            "confidence": confidence.item(),
            "label_id": label_id
        }
