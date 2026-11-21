"""Preserve source section scope when embedding and presenting short clauses."""

EMBEDDING_FORMAT = "section-content-v1"


def section_label(chunk) -> str | None:
    metadata = getattr(chunk, "chunk_metadata", None)
    part_title = getattr(chunk, "part_title", None)
    if not isinstance(part_title, str):
        part_title = metadata.get("part_title") if isinstance(metadata, dict) else None
    article_title = getattr(chunk, "article_title", None) or getattr(chunk, "section_title", None)
    titles = [title.strip() for title in (part_title, article_title)
              if isinstance(title, str) and title.strip()]
    return " / ".join(dict.fromkeys(titles)) or None


def reranker_text(chunk) -> str:
    heading = section_label(chunk)
    return f"{heading}\n{chunk.content}" if heading else chunk.content


def prepare_embedding_texts(chunks, embedding_service, max_tokens=512):
    texts = [reranker_text(chunk) for chunk in chunks]
    if any(embedding_service.count_document_tokens(text) > max_tokens for text in texts):
        raise ValueError("Contextual embedding input would be truncated")
    return texts
