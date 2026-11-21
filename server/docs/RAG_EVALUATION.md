# RAG Evaluation

## Evaluation Setup

- **System:** Good AI Advisor — Hybrid RAG
- **Dataset:** 26 Czech-language insurance questions
- **Source document:** VPP CP 2021
- **Retrieval:** E5 semantic search + lexical search + Stanza + RRF + CrossEncoder reranking
- **Evaluation method:** Article-level relevance matching
- **Git commit:** Add commit SHA from the evaluation run

## Retrieval Results

| Metric | Result |
|---|---:|
| Hit@1 | 69.23% (18/26) |
| Hit@3 | 84.62% (22/26) |
| Hit@5 | 100% (26/26) |
| MRR | 0.8038 |

All 26 evaluation questions retrieved at least one expected insurance article within the top five results.

## Performance

One observed retrieval execution:

| Stage | Latency |
|---|---:|
| Embedding | 0.020 s |
| Semantic search | 0.007 s |
| Original lexical search | 0.031 s |
| Stanza processing | 0.032 s |
| Stanza lexical search | 0.026 s |
| Reranker | 1.196 s |
| **Total retrieval** | **1.315 s** |

These timings represent one observed retrieval execution, not the average across all 26 queries.

## Limitations

- Evaluation covers 26 questions from one insurance document.
- Ground truth is defined at article level.
- Hit@5 does not establish that all conditions required for an answer have been retrieved.
- Results do not establish end-to-end answer correctness.
- Independent review and a broader evaluation dataset are required before making production reliability claims.git add server/docs/RAG_EVALUATION.md