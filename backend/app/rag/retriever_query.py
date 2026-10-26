"""Query construction and metadata ranking helpers for legacy local RAG."""

from typing import Any

from app.core.emotional_os import EmotionalOperatingState

AGE_KEYWORDS = {
    "teen": ["teen", "adolescent", "school", "exam", "peer", "parent"],
    "adult": ["adult", "work", "career", "relationship", "partner", "colleague"],
}


def build_query(user_text: str, eos: EmotionalOperatingState) -> str:
    """Build the search query from EOS labels and the user's words."""
    parts = [eos.surface_emotion, eos.modality.value if eos.modality else ""]
    if getattr(eos, "distortion_label", None):
        parts.append(eos.distortion_label)
    text_summary = " ".join(user_text.split()[:30])
    query = " ".join(part for part in parts if part)
    if text_summary:
        query += f" {text_summary}"
    return query.strip()


def age_score(meta: dict[str, Any], age_group: str | None) -> int:
    if not age_group:
        return 0
    keywords = AGE_KEYWORDS.get(age_group.lower(), [])
    if not keywords:
        return 0
    text = f"{meta.get('tags', '')} {meta.get('category', '')}".lower()
    return sum(1 for keyword in keywords if keyword in text)


def rerank_by_age_group(
    documents: list[str], metadatas: list[dict[str, Any]], age_group: str | None
) -> list[str]:
    if not age_group or not AGE_KEYWORDS.get(age_group.lower()):
        return documents
    order = sorted(
        range(len(documents)),
        key=lambda index: (
            -age_score(metadatas[index] if index < len(metadatas) else {}, age_group),
            index,
        ),
    )
    return [documents[index] for index in order]
