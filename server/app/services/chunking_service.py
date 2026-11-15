"""Build token-bounded chunks without crossing article boundaries."""

import re
from typing import Protocol

from app.schemas.knowledge_chunk import KnowledgeChunk
from app.schemas.structured_knowledge import KnowledgeBlock, StructuredKnowledgeDocument


class DocumentTokenCounter(Protocol):
    def count_document_tokens(self, text: str) -> int: ...


class ChunkingService:
    def __init__(self, embedding_service: DocumentTokenCounter, max_tokens: int = 400):
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.embedding_service = embedding_service
        self.max_tokens = max_tokens

    def _fits(self, text: str) -> bool:
        # Includes the E5 passage prefix and special tokens via EmbeddingService.
        return self.embedding_service.count_document_tokens(text) <= self.max_tokens

    def _split_large_text(self, text: str) -> list[str]:
        if self._fits(text):
            return [text]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            units = [sentence] if self._fits(sentence) else sentence.split()
            for unit in units:
                if not self._fits(unit):
                    raise ValueError(
                        "A single word exceeds max_tokens; increase the limit "
                        "or inspect the source document."
                    )
                candidate = f"{current} {unit}" if current else unit
                if self._fits(candidate):
                    current = candidate
                else:
                    pieces.append(current)
                    current = unit
        if current:
            pieces.append(current)
        return pieces

    def create_chunks(self, document: StructuredKnowledgeDocument) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for part in document.parts:
            for article in part.articles:
                texts: list[str] = []
                pages: set[int] = set()
                article_index = 0

                def flush() -> None:
                    nonlocal texts, pages, article_index
                    if not texts:
                        return
                    content = "\n".join(texts)
                    token_count = self.embedding_service.count_document_tokens(content)
                    if token_count > self.max_tokens:
                        raise ValueError("Chunk exceeds token limit")
                    chunks.append(KnowledgeChunk(
                        document_code=document.document.document_code,
                        part_code=part.code,
                        part_title=part.title,
                        article_number=article.number,
                        article_title=article.title,
                        source_pages=sorted(pages),
                        chunk_index=article_index,
                        token_count=token_count,
                        content=content,
                    ))
                    article_index += 1
                    texts, pages = [], set()

                blocks = article.blocks or [KnowledgeBlock(
                    text=article.content, pages=article.source_pages,
                )]
                for block in blocks:
                    text = block.text.strip()
                    if not text:
                        continue
                    for piece in self._split_large_text(text):
                        if texts and not self._fits("\n".join([*texts, piece])):
                            flush()
                        texts.append(piece)
                        pages.update(block.pages)
                flush()
        return chunks
