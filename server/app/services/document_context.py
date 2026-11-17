"""Preserve source section scope when searching and presenting short clauses."""


def section_label(chunk) -> str | None:
    metadata = getattr(chunk, "chunk_metadata", None)
    part_title = metadata.get("part_title") if isinstance(metadata, dict) else None
    titles = [title.strip() for title in (part_title, getattr(chunk, "section_title", None))
              if isinstance(title, str) and title.strip()]
    return " / ".join(dict.fromkeys(titles)) or None


def reranker_text(chunk) -> str:
    heading = section_label(chunk)
    return f"{heading}\n{chunk.content}" if heading else chunk.content
