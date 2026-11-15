from types import SimpleNamespace

import pytest

from app.schemas.structured_knowledge import KnowledgeArticle, KnowledgeBlock
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.structured_knowledge_loader import StructuredKnowledgeLoader
from scripts.validate_chunking import SOURCE, validate_document_chunks


class WordCounter:
    def count_document_tokens(self, text):
        return len(text.split()) + 3  # Account for prefix/special-token overhead.


def source_document(blocks, *, content="", second_article=False):
    article = KnowledgeArticle(
        number=1, start_page=1, title="Article one", source_pages=[1, 2],
        blocks=[KnowledgeBlock(text=text, pages=pages) for text, pages in blocks],
        content=content,
    )
    articles = [article]
    if second_article:
        articles.append(article.model_copy(update={"number": 2, "title": "Article two"}))
    return SimpleNamespace(
        document=SimpleNamespace(document_code="TEST"),
        parts=[SimpleNamespace(code="A", title="Part A", articles=articles)],
    )


def test_blocks_remain_whole_and_articles_never_merge():
    document = source_document([
        ("one two", [2, 1, 2]), ("three four", [2]), ("five six", [3]),
    ], second_article=True)
    chunks = ChunkingService(WordCounter(), 7).create_chunks(document)
    assert [chunk.content for chunk in chunks] == [
        "one two\nthree four", "five six", "one two\nthree four", "five six",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 0, 1]
    assert chunks[0].source_pages == [1, 2]
    validate_document_chunks(document, chunks, WordCounter(), 7)


@pytest.mark.parametrize("text", [
    "One two. Three four! Five six?",
    "one two three four five six seven eight nine ten",
    "První věta. Druhá věta obsahuje české znaky!",
])
def test_large_blocks_preserve_every_word_and_split_within_limit(text):
    document = source_document([(text, [4, 5])])
    chunks = ChunkingService(WordCounter(), 7).create_chunks(document)
    assert len(chunks) > 1
    assert all(chunk.source_pages == [4, 5] for chunk in chunks)
    validate_document_chunks(document, chunks, WordCounter(), 7)


def test_empty_blocks_are_ignored_and_content_fallback_is_supported():
    empty = source_document([("   ", [1])])
    assert ChunkingService(WordCounter()).create_chunks(empty) == []
    fallback = source_document([], content="Fallback article content")
    chunks = ChunkingService(WordCounter()).create_chunks(fallback)
    assert chunks[0].content == "Fallback article content"
    assert chunks[0].source_pages == [1, 2]
    validate_document_chunks(fallback, chunks, WordCounter(), 400)


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limits_fail_early(limit):
    with pytest.raises(ValueError, match="positive"):
        ChunkingService(WordCounter(), limit)


def test_unsplittable_word_fails_instead_of_silently_losing_text():
    counter = SimpleNamespace(count_document_tokens=lambda text: len(text) + 3)
    with pytest.raises(ValueError, match="single word"):
        ChunkingService(counter, 5).create_chunks(source_document([("abcdef", [1])]))


def test_real_structured_source_preserves_text_and_metadata_deterministically():
    document = StructuredKnowledgeLoader().load(str(SOURCE))
    service = ChunkingService(WordCounter(), 100)
    chunks = service.create_chunks(document)
    validate_document_chunks(document, chunks, WordCounter(), 100)
    assert chunks == service.create_chunks(document)
    assert len(chunks) >= 70


def test_production_counter_includes_passage_prefix_and_special_tokens():
    calls = []

    def tokenizer(text, **kwargs):
        calls.append((text, kwargs))
        return {"input_ids": [1, 2, 3, 4]}

    service = EmbeddingService.__new__(EmbeddingService)
    service.model = SimpleNamespace(tokenizer=tokenizer)
    assert service.count_document_tokens("example") == 4
    assert calls == [("passage: example", {"add_special_tokens": True, "truncation": False})]
