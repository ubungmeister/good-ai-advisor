"""
Creates embedding-safe chunks from structured knowledge documents.

Main rules:
- Never cross article boundaries.
- Keep prepared blocks together whenever possible.
- Final chunks must stay within max_tokens.
- If a single block is too large, split it by sentences.
- If a single sentence is still too large, split it by words.
"""

import re

from app.schemas.knowledge_chunk import KnowledgeChunk
from app.schemas.structured_knowledge import (
    KnowledgeArticle,
    KnowledgeBlock,
    StructuredKnowledgeDocument,
)
from app.services.embedding_service import EmbeddingService


class ChunkingService:
    """
    Converts structured insurance knowledge into chunks
    that are safe to send to the embedding model.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        max_tokens: int = 400,
    ):
        """
        embedding_service:
            Used to count tokens using the exact same tokenizer
            that our E5 embedding model uses.

        max_tokens:
            Maximum allowed size of one final chunk.
        """

        self.embedding_service = embedding_service
        self.max_tokens = max_tokens

    def create_chunks(
        self,
        document: StructuredKnowledgeDocument,
    ) -> list[KnowledgeChunk]:
        """
        Creates chunks for the whole document.

        We iterate through:
        document
            -> parts
                -> articles
                    -> blocks

        Each article is chunked independently.

        Important:
        chunks from different articles are never merged together.
        """

        chunks: list[KnowledgeChunk] = []

        for part in document.parts:
            for article in part.articles:
                article_chunks = self._chunk_article(
                    document_code=document.document.document_code,
                    part_code=part.code,
                    part_title=part.title,
                    article=article,
                )

                chunks.extend(article_chunks)

        return chunks

    def _chunk_article(
        self,
        document_code: str,
        part_code: str,
        part_title: str,
        article: KnowledgeArticle,
    ) -> list[KnowledgeChunk]:
        """
        Splits one article into one or more KnowledgeChunk objects.

        Main idea:

        block 1
        block 2
        block 3

        We keep adding blocks while:

            total_tokens <= max_tokens

        Example:

            block 1 = 120 tokens
            block 2 = 150 tokens

            combined = 270 tokens
            -> OK

            block 3 = 180 tokens

            combined = 450 tokens
            -> too large

        Result:

            chunk 0 = block 1 + block 2
            chunk 1 = block 3
        """

        chunks: list[KnowledgeChunk] = []

        # Text fragments currently being collected
        # for the next chunk.
        current_texts: list[str] = []

        # Pages associated with the current chunk.
        #
        # We use set so that pages are not duplicated.
        #
        # Example:
        # block 1 -> page 10
        # block 2 -> page 10
        #
        # result:
        # {10}
        current_pages: set[int] = set()

        for block in article.blocks:

            # A prepared block itself can theoretically
            # be larger than 400 tokens.
            #
            # In that case this method returns several smaller parts.
            block_parts = self._split_block_if_needed(block)

            for text, pages in block_parts:

                # Try adding the new text to our current chunk.
                candidate_texts = current_texts + [text]

                candidate_content = "\n".join(candidate_texts)

                candidate_token_count = (
                    self.embedding_service.count_document_tokens(
                        candidate_content
                    )
                )

                # If the new combined chunk still fits,
                # keep collecting text.
                if candidate_token_count <= self.max_tokens:
                    current_texts.append(text)
                    current_pages.update(pages)

                    continue

                # If adding the new block would exceed the limit,
                # finalize the previous chunk first.
                if current_texts:
                    chunks.append(
                        self._build_chunk(
                            document_code=document_code,
                            part_code=part_code,
                            part_title=part_title,
                            article=article,
                            chunk_index=len(chunks),
                            texts=current_texts,
                            pages=current_pages,
                        )
                    )

                # Start a completely new chunk
                # with the current block/fragment.
                current_texts = [text]
                current_pages = set(pages)

        # After the loop there may still be unfinished content
        # that never reached the token limit.
        #
        # We must save it as the final chunk.
        if current_texts:
            chunks.append(
                self._build_chunk(
                    document_code=document_code,
                    part_code=part_code,
                    part_title=part_title,
                    article=article,
                    chunk_index=len(chunks),
                    texts=current_texts,
                    pages=current_pages,
                )
            )

        return chunks

    def _split_block_if_needed(
        self,
        block: KnowledgeBlock,
    ) -> list[tuple[str, list[int]]]:
        """
        Checks whether one structured block fits inside max_tokens.

        If yes:
            return it unchanged.

        If no:
            split its text into smaller pieces.

        We keep original page metadata for all generated pieces.
        """

        token_count = (
            self.embedding_service.count_document_tokens(
                block.text
            )
        )

        # Normal case:
        # block already fits inside our limit.
        if token_count <= self.max_tokens:
            return [
                (
                    block.text,
                    block.pages,
                )
            ]

        # Oversized block:
        # split it into smaller textual pieces.
        text_parts = self._split_large_text(
            block.text
        )

        return [
            (
                text_part,
                block.pages,
            )
            for text_part in text_parts
        ]

    def _split_large_text(
        self,
        text: str,
    ) -> list[str]:
        """
        Splits a large block primarily by sentence boundaries.

        We prefer:

            sentence 1
            sentence 2
            sentence 3

        instead of blindly cutting text every N tokens.

        This preserves semantic meaning better.

        Only if a single sentence is itself too large
        do we fall back to splitting it by words.
        """

        # Very simple sentence boundary detection.
        #
        # Example:
        #
        # "First sentence. Second sentence!"
        #
        # becomes:
        #
        # [
        #     "First sentence.",
        #     "Second sentence!"
        # ]
        sentences = re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )

        result: list[str] = []

        # Sentences currently grouped together.
        current_sentences: list[str] = []

        for sentence in sentences:

            # Ignore accidental empty values.
            if not sentence.strip():
                continue

            candidate_sentences = (
                current_sentences + [sentence]
            )

            candidate_content = " ".join(
                candidate_sentences
            )

            candidate_token_count = (
                self.embedding_service.count_document_tokens(
                    candidate_content
                )
            )

            # New sentence still fits.
            if candidate_token_count <= self.max_tokens:
                current_sentences.append(sentence)

                continue

            # Current group is already non-empty,
            # so finalize it before handling this sentence.
            if current_sentences:
                result.append(
                    " ".join(current_sentences)
                )

                current_sentences = []

            # Now check the sentence itself.
            sentence_token_count = (
                self.embedding_service.count_document_tokens(
                    sentence
                )
            )

            # Sentence alone fits.
            #
            # Start a new group with it.
            if sentence_token_count <= self.max_tokens:
                current_sentences = [sentence]

                continue

            # Extremely long sentence.
            #
            # Rare, but possible in legal documents.
            #
            # Fall back to splitting it by words.
            word_chunks = self._split_by_words(
                sentence
            )

            result.extend(word_chunks)

        # Add remaining sentences.
        if current_sentences:
            result.append(
                " ".join(current_sentences)
            )

        return result

    def _split_by_words(
        self,
        text: str,
    ) -> list[str]:
        """
        Last-resort fallback.

        Used only when a single sentence itself
        is larger than max_tokens.

        We progressively add words until adding
        the next word would exceed the limit.
        """

        words = text.split()

        result: list[str] = []
        current_words: list[str] = []

        for word in words:

            candidate_words = (
                current_words + [word]
            )

            candidate_content = " ".join(
                candidate_words
            )

            candidate_token_count = (
                self.embedding_service.count_document_tokens(
                    candidate_content
                )
            )

            # Still fits.
            if candidate_token_count <= self.max_tokens:
                current_words.append(word)

                continue

            # Current group is full.
            if current_words:
                result.append(
                    " ".join(current_words)
                )

            # Start new group with the current word.
            current_words = [word]

        # Save remaining words.
        if current_words:
            result.append(
                " ".join(current_words)
            )

        return result

    def _build_chunk(
        self,
        document_code: str,
        part_code: str,
        part_title: str,
        article: KnowledgeArticle,
        chunk_index: int,
        texts: list[str],
        pages: set[int],
    ) -> KnowledgeChunk:
        """
        Builds the final KnowledgeChunk object.

        At this point the content should already
        satisfy our max_tokens rule.
        """

        content = "\n".join(texts)

        token_count = (
            self.embedding_service.count_document_tokens(
                content
            )
        )

        # Defensive validation.
        #
        # If this ever happens, there is a bug
        # somewhere in our chunking logic.
        if token_count > self.max_tokens:
            raise ValueError(
                "Chunk exceeds token limit: "
                f"{token_count} > {self.max_tokens}"
            )

        return KnowledgeChunk(
            document_code=document_code,
            part_code=part_code,
            part_title=part_title,
            article_number=article.number,
            article_title=article.title,
            source_pages=sorted(pages),
            chunk_index=chunk_index,
            token_count=token_count,
            content=content,
        )