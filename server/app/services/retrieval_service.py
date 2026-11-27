import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Sequence, TypeVar


T = TypeVar("T")


def _memory_snapshot(stage: str) -> None:
    """Print process and container memory without adding a runtime dependency."""
    process_memory = {}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in {"VmRSS", "VmHWM"}:
                process_memory[key] = f"{int(value.strip().split()[0]) / 1024:.1f}MiB"
    except (OSError, ValueError, IndexError):
        pass

    container_memory = {}
    cgroup_files = {
        "current": (
            "/sys/fs/cgroup/memory.current",
            "/sys/fs/cgroup/memory/memory.usage_in_bytes",
        ),
        "peak": (
            "/sys/fs/cgroup/memory.peak",
            "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
        ),
        "limit": (
            "/sys/fs/cgroup/memory.max",
            "/sys/fs/cgroup/memory/memory.limit_in_bytes",
        ),
    }
    for name, candidates in cgroup_files.items():
        for candidate in candidates:
            try:
                raw_value = Path(candidate).read_text().strip()
                if raw_value.isdigit():
                    container_memory[name] = f"{int(raw_value) / (1024 * 1024):.1f}MiB"
                elif raw_value == "max":
                    container_memory[name] = "unlimited"
                break
            except OSError:
                continue

    details = [f"{key}={value}" for key, value in process_memory.items()]
    details.extend(f"container_{key}={value}" for key, value in container_memory.items())
    print(f"MEMORY stage={stage} {' '.join(details) or 'metrics unavailable'}", flush=True)


def _load_component(name: str, factory: Callable[[], T]) -> T:
    """Sample memory while one retrieval component initializes."""
    stop_sampling = threading.Event()

    def sample_memory() -> None:
        while not stop_sampling.wait(5.0):
            _memory_snapshot(f"{name}_loading")

    started = time.perf_counter()
    print(f"RETRIEVAL_COMPONENT_START name={name}", flush=True)
    _memory_snapshot(f"before_{name}")
    sampler = threading.Thread(
        target=sample_memory,
        name=f"memory-{name}",
        daemon=True,
    )
    sampler.start()
    try:
        component = factory()
    except Exception:
        _memory_snapshot(f"failed_{name}")
        raise
    finally:
        stop_sampling.set()
        sampler.join(timeout=1.0)

    print(
        f"RETRIEVAL_COMPONENT_READY name={name} seconds={time.perf_counter() - started:.2f}",
        flush=True,
    )
    _memory_snapshot(f"after_{name}")
    return component

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
    """
    Hybrid retrieval service.

    Pipeline:

    Question
        |
        +--> Semantic E5 + pgvector -> Top20
        |
        +--> Original lexical pg_trgm -> Top20
        |
        +--> Stanza + synonyms -> pg_trgm -> Top20
                        |
                        v
                 RRF over all 3
                        |
                        +
              protected candidates
                        |
                        v
                max 16 candidates
                        |
                        v
                     reranker
                        |
                        v
                    Final Top K
    """

    # ==========================================================
    # Retrieval configuration
    # ==========================================================

    RRF_K = 20

    SEMANTIC_LIMIT = 20
    ORIGINAL_LEXICAL_LIMIT = 20
    STANZA_LEXICAL_LIMIT = 20

    # Keep strong semantic hits even if neither lexical channel agrees.
    SEMANTIC_PROTECTED = 5
    ORIGINAL_LEXICAL_PROTECTED = 2
    STANZA_LEXICAL_PROTECTED = 5

    # 5 semantic + 2 original lexical + 5 expanded lexical, with room for RRF.
    RERANKER_CANDIDATE_LIMIT = 16

    DEFAULT_FINAL_LIMIT = 5

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self):
        _memory_snapshot("retrieval_service_start")
        self.embedding_service = _load_component(
            "embedding_model", EmbeddingService,
        )
        self.document_chunk_repository = DocumentChunkRepository()
        self.lexical_query_builder = _load_component(
            "stanza_pipeline", LexicalQueryBuilder,
        )
        self.reranker_service = _load_component(
            "cross_encoder", RerankerService,
        )
        _memory_snapshot("retrieval_service_ready")

    # ==========================================================
    # SEARCH
    # ==========================================================

    def search(
        self,
        db: Session,
        question: str,
        limit: int = DEFAULT_FINAL_LIMIT,
        *,
        product_version_id: uuid.UUID,
    ) -> Sequence[
        tuple[DocumentChunk, float]
    ]:
        """
        Run the complete hybrid retrieval pipeline.

        This version contains detailed diagnostic output
        so we can find exactly where retrieval is hanging.
        """

        total_start = time.perf_counter()

        print(
            "\n========================================",
            flush=True,
        )
        print(
            "RETRIEVAL DEBUG START",
            flush=True,
        )
        print(
            "========================================",
            flush=True,
        )

        # ======================================================
        # STAGE 1
        # EMBEDDING
        # ======================================================

        print(
            "\nR1. EMBEDDING START",
            flush=True,
        )

        embedding_start = (
            time.perf_counter()
        )

        query_embedding = (
            self.embedding_service.embed_query(
                question
            )
        )

        embedding_time = (
            time.perf_counter()
            - embedding_start
        )

        print(
            "R1. EMBEDDING DONE",
            flush=True,
        )

        print(
            f"R1 TIME: "
            f"{embedding_time:.3f} sec",
            flush=True,
        )

        print(
            "EMBEDDING DIMENSIONS:",
            len(query_embedding),
            flush=True,
        )

        # ======================================================
        # STAGE 2
        # SEMANTIC SEARCH
        # ======================================================

        print(
            "\nR2. SEMANTIC SEARCH START",
            flush=True,
        )

        semantic_start = (
            time.perf_counter()
        )

        semantic_results = list(
            self.document_chunk_repository.search_similar(
                db=db,
                embedding=query_embedding,
                limit=self.SEMANTIC_LIMIT,
                product_version_id=product_version_id,
            )
        )

        semantic_time = (
            time.perf_counter()
            - semantic_start
        )

        print(
            "R2. SEMANTIC SEARCH DONE",
            flush=True,
        )

        print(
            f"R2 TIME: "
            f"{semantic_time:.3f} sec",
            flush=True,
        )

        print(
            "SEMANTIC RESULTS:",
            len(semantic_results),
            flush=True,
        )

        # ======================================================
        # STAGE 3
        # ORIGINAL LEXICAL SEARCH
        # ======================================================

        print(
            "\nR3. ORIGINAL LEXICAL START",
            flush=True,
        )

        original_lexical_start = (
            time.perf_counter()
        )

        original_lexical_results = list(
            self.document_chunk_repository.search_lexical(
                db=db,
                question=question,
                limit=self.ORIGINAL_LEXICAL_LIMIT,
                product_version_id=product_version_id,
            )
        )

        original_lexical_time = (
            time.perf_counter()
            - original_lexical_start
        )

        print(
            "R3. ORIGINAL LEXICAL DONE",
            flush=True,
        )

        print(
            f"R3 TIME: "
            f"{original_lexical_time:.3f} sec",
            flush=True,
        )

        print(
            "ORIGINAL LEXICAL RESULTS:",
            len(original_lexical_results),
            flush=True,
        )

        # ======================================================
        # STAGE 4
        # STANZA / LEXICAL QUERY BUILDER
        # ======================================================

        print(
            "\nR4. STANZA BUILD START",
            flush=True,
        )

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

        print(
            "R4. STANZA BUILD DONE",
            flush=True,
        )

        print(
            f"R4 TIME: "
            f"{lexical_builder_time:.3f} sec",
            flush=True,
        )


        # ======================================================
        # STAGE 5
        # STANZA LEXICAL SEARCH
        # ======================================================

        print(
            "\nR5. STANZA LEXICAL START",
            flush=True,
        )

        stanza_lexical_start = (
            time.perf_counter()
        )

        stanza_lexical_results = list(
            self.document_chunk_repository.search_lexical(
                db=db,
                question=stanza_query,
                limit=self.STANZA_LEXICAL_LIMIT,
                product_version_id=product_version_id,
            )
        )

        stanza_lexical_time = (
            time.perf_counter()
            - stanza_lexical_start
        )

        print(
            "R5. STANZA LEXICAL DONE",
            flush=True,
        )

        print(
            f"R5 TIME: "
            f"{stanza_lexical_time:.3f} sec",
            flush=True,
        )

        print(
            "STANZA LEXICAL RESULTS:",
            len(stanza_lexical_results),
            flush=True,
        )

        # ======================================================
        # STAGE 6
        # RECIPROCAL RANK FUSION
        # ======================================================

        print(
            "\nR6. RRF START",
            flush=True,
        )

        fusion_start = (
            time.perf_counter()
        )

        fused_results = (
            self._fuse_retrieval_results(
                result_lists=[
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

        print(
            "R6. RRF DONE",
            flush=True,
        )

        print(
            f"R6 TIME: "
            f"{fusion_time:.3f} sec",
            flush=True,
        )

        print(
            "FUSED RESULTS:",
            len(fused_results),
            flush=True,
        )

        # ======================================================
        # STAGE 7
        # CANDIDATE SELECTION
        # ======================================================

        print(
            "\nR7. CANDIDATE SELECTION START",
            flush=True,
        )

        candidate_start = (
            time.perf_counter()
        )

        candidates = (
            self._build_protected_candidates(
                semantic_results=(
                    semantic_results
                ),
                original_lexical_results=(
                    original_lexical_results
                ),
                stanza_lexical_results=(
                    stanza_lexical_results
                ),
                fused_results=(
                    fused_results
                ),
            )
        )

        candidate_time = (
            time.perf_counter()
            - candidate_start
        )

        print(
            "R7. CANDIDATE SELECTION DONE",
            flush=True,
        )

        print(
            f"R7 TIME: "
            f"{candidate_time:.3f} sec",
            flush=True,
        )

        print(
            "CANDIDATES FOR RERANKER:",
            len(candidates),
            flush=True,
        )

        # ======================================================
        # STAGE 8
        # RERANKER
        # ======================================================

        print(
            "\nR8. RERANKER START",
            flush=True,
        )

        reranker_start = (
            time.perf_counter()
        )

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

        print(
            "R8. RERANKER DONE",
            flush=True,
        )

        print(
            f"R8 TIME: "
            f"{reranker_time:.3f} sec",
            flush=True,
        )

        print(
            "RERANKED RESULTS:",
            len(reranked),
            flush=True,
        )

        # ======================================================
        # STAGE 9
        # FINAL TOP K
        # ======================================================

        print(
            "\nR9. FINAL TOP K START",
            flush=True,
        )

        final_results = (
            reranked[:limit]
        )

        print(
            "R9. FINAL TOP K DONE",
            flush=True,
        )

        print(
            "FINAL RESULTS:",
            len(final_results),
            flush=True,
        )

        # ======================================================
        # TOTAL
        # ======================================================

        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            "\n----------------------------------------",
            flush=True,
        )

        print(
            "RETRIEVAL TIMINGS",
            flush=True,
        )

        print(
            "----------------------------------------",
            flush=True,
        )

        print(
            f"Embedding:          "
            f"{embedding_time:.3f} sec",
            flush=True,
        )

        print(
            f"Semantic search:    "
            f"{semantic_time:.3f} sec",
            flush=True,
        )

        print(
            f"Original lexical:   "
            f"{original_lexical_time:.3f} sec",
            flush=True,
        )

        print(
            f"Stanza builder:     "
            f"{lexical_builder_time:.3f} sec",
            flush=True,
        )

        print(
            f"Stanza lexical:     "
            f"{stanza_lexical_time:.3f} sec",
            flush=True,
        )

        print(
            f"RRF fusion:         "
            f"{fusion_time:.3f} sec",
            flush=True,
        )

        print(
            f"Candidate selection:"
            f" {candidate_time:.3f} sec",
            flush=True,
        )

        print(
            f"Reranker:           "
            f"{reranker_time:.3f} sec",
            flush=True,
        )

        print(
            f"TOTAL RETRIEVAL:    "
            f"{total_time:.3f} sec",
            flush=True,
        )

        print(
            "========================================",
            flush=True,
        )

        print(
            "RETRIEVAL DEBUG COMPLETE",
            flush=True,
        )

        print(
            "========================================\n",
            flush=True,
        )

        return final_results

    # ==========================================================
    # RRF
    # ==========================================================

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
        Reciprocal Rank Fusion across all retrievers.

        Formula for every occurrence:

            score += 1 / (RRF_K + rank)

        Raw E5 and lexical scores are not mixed directly.
        """

        scores: dict[
            object,
            float,
        ] = {}

        chunks_by_id: dict[
            object,
            DocumentChunk,
        ] = {}

        # ------------------------------------------------------
        # Each retriever contributes independently.
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Convert dictionary back to ranked list.
        # ------------------------------------------------------

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

    # ==========================================================
    # PROTECTED CANDIDATES
    # ==========================================================

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
        Build maximum 16 unique candidates.

        Protection:

        - Semantic Top5
        - Original lexical Top2
        - Stanza lexical Top5

        Remaining positions are filled using RRF order.
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
            """
            Add one chunk unless:

            - it is already selected
            - candidate limit has been reached
            """

            if chunk.id in selected_ids:
                return

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

        # ======================================================
        # 1. Protect strong semantic candidates
        # ======================================================

        for chunk, _ in semantic_results[
            :self.SEMANTIC_PROTECTED
        ]:

            add_candidate(
                chunk
            )

        # ======================================================
        # 2. Protect Original lexical Top2
        # ======================================================

        for chunk, _ in original_lexical_results[
            :self.ORIGINAL_LEXICAL_PROTECTED
        ]:

            add_candidate(
                chunk
            )

        # ======================================================
        # 3. Protect Stanza lexical Top5
        # ======================================================

        for chunk, _ in stanza_lexical_results[
            :self.STANZA_LEXICAL_PROTECTED
        ]:

            add_candidate(
                chunk
            )

        # ======================================================
        # 4. Fill remaining positions using RRF
        # ======================================================

        for chunk, _ in fused_results:

            if (
                len(selected_chunks)
                >= self.RERANKER_CANDIDATE_LIMIT
            ):
                break

            add_candidate(
                chunk
            )

        # ======================================================
        # Attach RRF score to candidates
        # ======================================================

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
