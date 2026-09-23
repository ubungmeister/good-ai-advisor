import time
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.services.embedding_service import EmbeddingService
from app.services.lexical_query_builder import (
    LexicalQueryBuilder,
)
from app.services.reranker_service import RerankerService


class RetrievalService:

    # ==========================================================
    # Retrieval configuration
    # ==========================================================

    RRF_K = 20

    SEMANTIC_LIMIT = 20
    ORIGINAL_LEXICAL_LIMIT = 20
    STANZA_LEXICAL_LIMIT = 20

    # Protected candidates.
    #
    # These candidates cannot be lost only because
    # their final RRF rank is lower than Top 12.
    SEMANTIC_PROTECTED = 2
    ORIGINAL_LEXICAL_PROTECTED = 2
    STANZA_LEXICAL_PROTECTED = 5

    # Expensive cross-encoder only sees 12 chunks.
    RERANKER_CANDIDATE_LIMIT = 12

    # Default number of chunks returned to caller / LLM.
    DEFAULT_FINAL_LIMIT = 5

    def __init__(self):
        self.embedding_service = EmbeddingService()

        self.document_chunk_repository = (
            DocumentChunkRepository()
        )

        self.lexical_query_builder = (
            LexicalQueryBuilder()
        )

        self.reranker_service = (
            RerankerService()
        )

    def search(
        self,
        db: Session,
        question: str,
        limit: int = DEFAULT_FINAL_LIMIT,
    ) -> Sequence[
        tuple[DocumentChunk, float]
    ]:
        """
        Final hybrid retrieval pipeline.

        Question
            |
            +--> E5 semantic search
            |       Top 20
            |
            +--> Original lexical search
            |       Top 20
            |
            +--> Stanza + synonyms lexical search
                    Top 20

                        |
                        v

                RRF over all 3 lists

                        +

                Protected candidates:
                    Semantic Top 2
                    Original lexical Top 2
                    Stanza lexical Top 5

                        |
                        v

                Max 12 unique candidates

                        |
                        v

                    MiniLM reranker

                        |
                        v

                    Final Top K
        """

        total_start = time.perf_counter()

        # ======================================================
        # Stage 1
        # Question embedding
        # ======================================================

        embedding_start = time.perf_counter()

        query_embedding = (
            self.embedding_service.embed_query(
                question
            )
        )

        embedding_time = (
            time.perf_counter()
            - embedding_start
        )

        # ======================================================
        # Stage 2
        # Semantic retrieval
        #
        # E5 embedding
        #     ->
        # pgvector cosine similarity
        #     ->
        # Top 20
        # ======================================================

        semantic_start = time.perf_counter()

        semantic_results = list(
            self.document_chunk_repository.search_similar(
                db=db,
                embedding=query_embedding,
                limit=self.SEMANTIC_LIMIT,
            )
        )

        semantic_time = (
            time.perf_counter()
            - semantic_start
        )

        # ======================================================
        # Stage 3
        # Original lexical retrieval
        #
        # Full original question
        #     ->
        # PostgreSQL pg_trgm / word_similarity
        #     ->
        # Top 20
        # ======================================================

        original_lexical_start = (
            time.perf_counter()
        )

        original_lexical_results = list(
            self.document_chunk_repository.search_lexical(
                db=db,
                question=question,
                limit=self.ORIGINAL_LEXICAL_LIMIT,
            )
        )

        original_lexical_time = (
            time.perf_counter()
            - original_lexical_start
        )

        # ======================================================
        # Stage 4
        # Build focused lexical query
        #
        # Example:
        #
        # "Je cestovní pas pojištěný
        #  v rámci pojištění zavazadel?"
        #
        # becomes:
        #
        # "cestovní pas zavazadlo"
        #
        # Stanza performs:
        # - tokenization
        # - POS filtering
        # - lemmatization
        # - noise removal
        # - synonym expansion
        # ======================================================

        lexical_builder_start = (
            time.perf_counter()
        )

        stanza_query = (
            self.lexical_query_builder.build(
                question
            )
        )

        lexical_builder_time = (
            time.perf_counter()
            - lexical_builder_start
        )

        # ======================================================
        # Stage 5
        # Stanza lexical retrieval
        #
        # Focused query
        #     ->
        # pg_trgm / word_similarity
        #     ->
        # Top 20
        # ======================================================

        stanza_lexical_start = (
            time.perf_counter()
        )

        stanza_lexical_results = list(
            self.document_chunk_repository.search_lexical(
                db=db,
                question=stanza_query,
                limit=self.STANZA_LEXICAL_LIMIT,
            )
        )

        stanza_lexical_time = (
            time.perf_counter()
            - stanza_lexical_start
        )

        # ======================================================
        # Stage 6
        # Reciprocal Rank Fusion
        #
        # ALL Top20 lists participate:
        #
        # Semantic Top20
        # Original lexical Top20
        # Stanza lexical Top20
        #
        # Formula:
        #
        # score += 1 / (RRF_K + rank)
        #
        # We use ranks instead of raw scores because:
        #
        # E5 cosine score
        # !=
        # pg_trgm similarity score
        #
        # Their numeric scales cannot safely be compared.
        # ======================================================

        fusion_start = time.perf_counter()

        fused_results = (
            self._fuse_retrieval_results(
                [
                    semantic_results,
                    original_lexical_results,
                    stanza_lexical_results,
                ]
            )
        )

        fusion_time = (
            time.perf_counter()
            - fusion_start
        )

        # ======================================================
        # Stage 7
        # Protected candidate selection
        #
        # RRF alone can lose a very strong candidate from
        # one retriever.
        #
        # Example:
        #
        # Stanza lexical #1
        #
        # but because other chunks appear in multiple lists,
        # RRF could put it below overall Top12.
        #
        # Therefore protect:
        #
        # Semantic Top2
        # Original lexical Top2
        # Stanza lexical Top5
        #
        # Then fill remaining places from RRF.
        #
        # Final candidate count is STILL max 12.
        # ======================================================

        candidate_start = time.perf_counter()

        candidates = (
            self._build_protected_candidates(
                semantic_results=semantic_results,
                original_lexical_results=(
                    original_lexical_results
                ),
                stanza_lexical_results=(
                    stanza_lexical_results
                ),
                fused_results=fused_results,
            )
        )

        candidate_time = (
            time.perf_counter()
            - candidate_start
        )

        # ======================================================
        # Stage 8
        # Cross-encoder reranker
        #
        # The candidate pool is NOT the final ranking.
        #
        # MiniLM evaluates:
        #
        # (question, chunk)
        #
        # for every candidate and creates a new ranking.
        # ======================================================

        reranker_start = time.perf_counter()

        reranked = (
            self.reranker_service.rerank(
                question=question,
                candidates=candidates,
                limit=self.RERANKER_CANDIDATE_LIMIT,
            )
        )

        reranker_time = (
            time.perf_counter()
            - reranker_start
        )

        # ======================================================
        # Stage 9
        # Final Top K
        # ======================================================

        final_results = reranked[:limit]

        # ======================================================
        # Timing
        # ======================================================

        total_time = (
            time.perf_counter()
            - total_start
        )

        print()
        print(
            "----------------------------------------"
        )

        print(
            "RETRIEVAL TIMINGS"
        )

        print(
            "----------------------------------------"
        )

        print(
            f"Embedding: "
            f"{embedding_time:.3f}s"
        )

        print(
            f"Semantic search: "
            f"{semantic_time:.3f}s"
        )

        print(
            f"Original lexical: "
            f"{original_lexical_time:.3f}s"
        )

        print(
            f"Lexical builder: "
            f"{lexical_builder_time:.3f}s"
        )

        print(
            f"Stanza lexical: "
            f"{stanza_lexical_time:.3f}s"
        )

        print(
            f"RRF fusion: "
            f"{fusion_time:.3f}s"
        )

        print(
            f"Candidate selection: "
            f"{candidate_time:.3f}s"
        )

        print(
            f"Reranker: "
            f"{reranker_time:.3f}s"
        )

        print(
            f"Candidates: "
            f"{len(candidates)}"
        )

        print(
            f"Final results: "
            f"{len(final_results)}"
        )

        print(
            f"TOTAL retrieval: "
            f"{total_time:.3f}s"
        )

        print(
            "----------------------------------------"
        )

        return final_results

    def _fuse_retrieval_results(
        self,
        result_lists: list[
            Sequence[
                tuple[
                    DocumentChunk,
                    float,
                ]
            ]
        ],
    ) -> list[
        tuple[
            DocumentChunk,
            float,
        ]
    ]:
        """
        Reciprocal Rank Fusion across any number
        of retriever result lists.

        Current lists:

        1. Semantic E5
        2. Original lexical
        3. Stanza lexical

        Example:

        Semantic:
            A #1
            B #2
            C #3

        Original lexical:
            B #1
            D #2

        Stanza:
            C #1
            B #2

        B receives RRF points from all three lists,
        therefore its combined score becomes high.
        """

        scores: dict[
            object,
            float,
        ] = {}

        chunks_by_id: dict[
            object,
            DocumentChunk,
        ] = {}

        for results in result_lists:

            for rank, (
                chunk,
                _,
            ) in enumerate(
                results,
                start=1,
            ):
                chunks_by_id[
                    chunk.id
                ] = chunk

                if chunk.id not in scores:
                    scores[
                        chunk.id
                    ] = 0.0

                scores[
                    chunk.id
                ] += (
                    1.0
                    / (
                        self.RRF_K
                        + rank
                    )
                )

        fused_results = [
            (
                chunks_by_id[
                    chunk_id
                ],
                score,
            )
            for chunk_id, score
            in scores.items()
        ]

        fused_results.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return fused_results

    def _build_protected_candidates(
        self,
        semantic_results: Sequence[
            tuple[
                DocumentChunk,
                float,
            ]
        ],
        original_lexical_results: Sequence[
            tuple[
                DocumentChunk,
                float,
            ]
        ],
        stanza_lexical_results: Sequence[
            tuple[
                DocumentChunk,
                float,
            ]
        ],
        fused_results: Sequence[
            tuple[
                DocumentChunk,
                float,
            ]
        ],
    ) -> list[
        tuple[
            DocumentChunk,
            float,
        ]
    ]:
        """
        Build final candidate pool for reranker.

        Strategy:

        1. Protect Semantic Top2.
        2. Protect Original lexical Top2.
        3. Protect Stanza lexical Top5.
        4. Remove duplicates.
        5. Fill remaining positions from RRF.
        6. Stop at maximum 12 unique chunks.

        Important:

        Protected does NOT mean that a chunk will
        appear in the final Top5.

        It only guarantees that the reranker gets
        the opportunity to evaluate that chunk.
        """

        selected_chunks: list[
            DocumentChunk
        ] = []

        selected_ids: set[
            object
        ] = set()

        def add_candidate(
            chunk: DocumentChunk,
        ) -> None:

            # Do not add duplicate chunk.
            if chunk.id in selected_ids:
                return

            # Never send more than 12 candidates.
            if (
                len(selected_chunks)
                >= self.RERANKER_CANDIDATE_LIMIT
            ):
                return

            selected_chunks.append(
                chunk
            )

            selected_ids.add(
                chunk.id
            )

        # ==================================================
        # Protect Semantic Top2
        # ==================================================

        for chunk, _ in semantic_results[
            :self.SEMANTIC_PROTECTED
        ]:
            add_candidate(
                chunk
            )

        # ==================================================
        # Protect Original Lexical Top2
        # ==================================================

        for chunk, _ in original_lexical_results[
            :self.ORIGINAL_LEXICAL_PROTECTED
        ]:
            add_candidate(
                chunk
            )

        # ==================================================
        # Protect Stanza Lexical Top5
        # ==================================================

        for chunk, _ in stanza_lexical_results[
            :self.STANZA_LEXICAL_PROTECTED
        ]:
            add_candidate(
                chunk
            )

        # ==================================================
        # Fill remaining places using RRF ranking.
        #
        # Example:
        #
        # protected unique = 8
        #
        # 12 - 8 = 4
        #
        # Therefore take next 4 unique candidates
        # from RRF.
        # ==================================================

        for chunk, _ in fused_results:

            if (
                len(selected_chunks)
                >= self.RERANKER_CANDIDATE_LIMIT
            ):
                break

            add_candidate(
                chunk
            )

        # ==================================================
        # Reranker API expects:
        #
        # (DocumentChunk, score)
        #
        # Protected candidates may have been selected
        # outside RRF Top12, but they still have an RRF
        # score because all three Top20 lists participated
        # in RRF.
        # ==================================================

        rrf_scores_by_id = {
            chunk.id: score
            for chunk, score
            in fused_results
        }

        candidates = [
            (
                chunk,
                rrf_scores_by_id.get(
                    chunk.id,
                    0.0,
                ),
            )
            for chunk
            in selected_chunks
        ]

        return candidates