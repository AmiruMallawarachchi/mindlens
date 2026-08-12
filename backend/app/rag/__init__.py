"""MindLens RAG (Retrieval-Augmented Generation) package.

Provides ChromaDB vector store, ingestion pipeline, and MMR retriever
for grounding therapy responses in evidence-based clinical knowledge.
"""

from app.rag.ingest import ingest_documents
from app.rag.retriever import TherapyRetriever, get_retriever
from app.rag.vector_store import TherapyVectorStore, get_vector_store

__all__ = [
    "TherapyVectorStore",
    "get_vector_store",
    "TherapyRetriever",
    "get_retriever",
    "ingest_documents",
]
