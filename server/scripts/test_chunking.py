from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.structured_knowledge_loader import (
    StructuredKnowledgeLoader,
)


MAX_TOKENS = 400


def main():
    # Loads and validates our prepared JSON document.
    loader = StructuredKnowledgeLoader()

    # We need EmbeddingService because it contains
    # the E5 tokenizer used for exact token counting.
    embedding_service = EmbeddingService()

    # Service responsible for converting articles
    # into embedding-safe chunks.
    chunking_service = ChunkingService(
        embedding_service=embedding_service,
        max_tokens=MAX_TOKENS,
    )

    # Load the prepared insurance knowledge document.
    document = loader.load(
        "data/knowledge/processed/vpp_cp_2021_structured.json"
    )

    # Convert all document articles into chunks.
    chunks = chunking_service.create_chunks(document)

    # Find chunks that violate our 400-token limit.
    oversized_chunks = [
        chunk
        for chunk in chunks
        if chunk.token_count > MAX_TOKENS
    ]

    # Sort chunks from largest to smallest
    # so we can inspect the most interesting ones.
    largest_chunks = sorted(
        chunks,
        key=lambda chunk: chunk.token_count,
        reverse=True,
    )

    print("=== CHUNKING RESULT ===")
    print()

    print(f"Total chunks: {len(chunks)}")
    print(f"Oversized chunks: {len(oversized_chunks)}")

    print()
    print("Largest chunks:")
    print()

    for chunk in largest_chunks[:10]:
        print(
            f"{chunk.token_count:>4} tokens | "
            f"Part {chunk.part_code} | "
            f"Article {chunk.article_number} | "
            f"Chunk {chunk.chunk_index} | "
            f"Pages {chunk.source_pages}"
        )

    print()
    print("=== VALIDATION ===")
    print()

    if oversized_chunks:
        print(
            f"ERROR: Found {len(oversized_chunks)} "
            f"chunks larger than {MAX_TOKENS} tokens."
        )

        print()

        for chunk in oversized_chunks:
            print(
                f"{chunk.token_count} tokens | "
                f"Part {chunk.part_code} | "
                f"Article {chunk.article_number} | "
                f"Chunk {chunk.chunk_index}"
            )
    else:
        print(
            f"OK: All chunks are <= {MAX_TOKENS} tokens."
        )


if __name__ == "__main__":
    main()