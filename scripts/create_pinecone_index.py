"""Create the Pinecone hosted-embedding index used by MindLens V2."""

from __future__ import annotations

import os

from pinecone import Pinecone


def main() -> None:
    api_key = os.environ["PINECONE_API_KEY"]
    index_name = os.environ["PINECONE_INDEX_NAME"]
    model = os.getenv("PINECONE_EMBEDDING_MODEL", "llama-text-embed-v2")
    client = Pinecone(api_key=api_key)
    names = {item["name"] for item in client.list_indexes()}
    if index_name in names:
        print(f"Pinecone index {index_name} already exists.")
        return
    client.create_index_for_model(
        name=index_name,
        cloud="aws",
        region=os.getenv("PINECONE_REGION", "us-east-1"),
        embed={"model": model, "field_map": {"text": "text"}},
    )
    print(f"Created Pinecone hosted-embedding index {index_name} using {model}.")


if __name__ == "__main__":
    main()
