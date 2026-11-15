"""Validate the actual source with the E5 tokenizer, without a database or LLM."""

import argparse
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EMBEDDING_MODEL_NAME, EmbeddingService
from app.services.structured_knowledge_loader import StructuredKnowledgeLoader

SOURCE = Path(__file__).resolve().parents[1] / "data/knowledge/processed/vpp_cp_2021_structured.json"


def validate_document_chunks(document, chunks, counter, max_tokens):
    """Check preservation independently of the splitting implementation."""
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[(chunk.part_code, chunk.article_number)].append(chunk)
        if chunk.document_code != document.document.document_code:
            raise ValueError("Wrong document code")
        if not chunk.content.strip():
            raise ValueError("Empty chunk")
        actual_count = counter.count_document_tokens(chunk.content)
        if chunk.token_count != actual_count or actual_count > max_tokens:
            raise ValueError("Incorrect token count or oversized chunk")

    article_keys = set()
    for part in document.parts:
        for article in part.articles:
            key = (part.code, article.number)
            if key in article_keys:
                raise ValueError(f"Duplicate source article identity: {key}")
            article_keys.add(key)
            article_chunks = grouped.pop(key, [])
            source = "\n".join(block.text for block in article.blocks) if article.blocks else article.content
            output = "\n".join(chunk.content for chunk in article_chunks)
            if source.split() != output.split():
                raise ValueError(f"Lost, duplicated or reordered article text: {key}")
            expected_pages = {
                page for block in article.blocks if block.text.strip() for page in block.pages
            } if article.blocks else set(article.source_pages) if source.strip() else set()
            actual_pages = {page for chunk in article_chunks for page in chunk.source_pages}
            if expected_pages != actual_pages:
                raise ValueError(f"Changed page metadata: {key}")
            for index, chunk in enumerate(article_chunks):
                if (chunk.chunk_index != index or chunk.article_title != article.title
                        or chunk.part_title != part.title):
                    raise ValueError(f"Changed article metadata or chunk order: {key}")
                if chunk.source_pages != sorted(set(chunk.source_pages)):
                    raise ValueError(f"Unsorted or duplicate pages: {key}")
    if grouped:
        raise ValueError("Chunks refer to articles absent from the source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-files-only", action="store_true", help="Use only cached tokenizer files.")
    args = parser.parse_args()
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        EMBEDDING_MODEL_NAME, local_files_only=args.local_files_only,
    )
    # Exercise production token counting, including the passage prefix and specials,
    # without loading the embedding model's weights.
    counter = EmbeddingService.__new__(EmbeddingService)
    counter.model = SimpleNamespace(tokenizer=tokenizer)
    document = StructuredKnowledgeLoader().load(str(SOURCE))
    chunks = ChunkingService(counter, max_tokens=400).create_chunks(document)
    validate_document_chunks(document, chunks, counter, 400)
    print(f"PASS: {len(document.parts)} parts, "
          f"{sum(len(part.articles) for part in document.parts)} articles, {len(chunks)} chunks")
    print(f"Largest chunk: {max(chunk.token_count for chunk in chunks)} / 400 tokens")
    print("Text order, article boundaries, page metadata and E5 token counts verified.")


if __name__ == "__main__":
    main()
