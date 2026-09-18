from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.structured_knowledge_loader import (
    StructuredKnowledgeLoader,
)


EXPECTED_EMBEDDING_DIMENSIONS = 384
MAX_TOKENS = 400


def main():
    # Load our prepared and validated insurance document.
    loader = StructuredKnowledgeLoader()

    # E5 model used both for token counting
    # and for creating embeddings.
    embedding_service = EmbeddingService()

    # Create embedding-safe chunks.
    chunking_service = ChunkingService(
        embedding_service=embedding_service,
        max_tokens=MAX_TOKENS,
    )

    document = loader.load(
        "data/knowledge/processed/vpp_cp_2021_structured.json"
    )

    chunks = chunking_service.create_chunks(
        document
    )

    print("=== EMBEDDING TEST ===")
    print()

    print(f"Chunks created: {len(chunks)}")

    # Extract only text because this is what E5 needs
    # to create the vectors.
    texts = [
        chunk.content
        for chunk in chunks
    ]

    print("Creating embeddings...")

    embeddings = embedding_service.embed_documents(
        texts
    )

    print(f"Embeddings created: {len(embeddings)}")

    # We must get exactly one embedding
    # for every KnowledgeChunk.
    if len(chunks) != len(embeddings):
        raise ValueError(
            "Chunk / embedding count mismatch: "
            f"{len(chunks)} chunks, "
            f"{len(embeddings)} embeddings"
        )

    invalid_embeddings = []

    for index, embedding in enumerate(embeddings):
        if len(embedding) != EXPECTED_EMBEDDING_DIMENSIONS:
            invalid_embeddings.append(
                (
                    index,
                    len(embedding),
                )
            )

    print()
    print("=== VALIDATION ===")
    print()

    if invalid_embeddings:
        print(
            f"ERROR: Found {len(invalid_embeddings)} "
            "embeddings with invalid dimensions."
        )

        for index, dimensions in invalid_embeddings:
            print(
                f"Chunk {index}: "
                f"{dimensions} dimensions"
            )
    else:
        print(
            f"OK: All {len(embeddings)} embeddings "
            f"have {EXPECTED_EMBEDDING_DIMENSIONS} dimensions."
        )

    # Show one example so that we can visually
    # confirm what an embedding looks like.
    if embeddings:
        first_embedding = embeddings[0]

        print()
        print("Example:")
        print(
            f"Chunk 0 tokens: "
            f"{chunks[0].token_count}"
        )
        print(
            f"Embedding dimensions: "
            f"{len(first_embedding)}"
        )
        print(
            f"First 5 values: "
            f"{first_embedding[:5]}"
        )


if __name__ == "__main__":
    main()