# RAG Evaluation

This report evaluates retrieval quality for Good AI Advisor's travel-insurance document search. It measures whether the expected policy article is retrieved, **not** whether the final assistant answer is correct or whether a claim is payable.

## Evaluation setup

| Item | Configuration |
| --- | --- |
| Corpus | VPP CP 2021 (one Czech-language insurance terms document) |
| Dataset | 26 Czech-language questions in `server/data/evals/retrieval_eval.json` |
| Ground truth | One or more expected article numbers per question |
| Matching | An expected article must occur in the scoped source document; the best matching rank is used |
| Metrics | Hit@1, Hit@3, Hit@5, MRR@10 |
| Evaluation depth | Top 10 retrieved chunks, matched at article level |
| Production retrieval | Three retrieval channels, RRF, protected candidate selection (maximum 16), CrossEncoder reranking |

The comparison runs the **same 26 questions** against three ranking strategies and reuses the same initial retrieval results for each question. The database lookup is product-version scoped and read-only.

## Comparative results

| Retrieval strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Mean stage-derived time* |
| --- | ---: | ---: | ---: | ---: | ---: |
| E5 semantic only | 57.7% (15/26) | 69.2% (18/26) | 80.8% (21/26) | 0.664 | 0.052 s |
| E5 + lexical + Stanza, fused with RRF | 57.7% (15/26) | 69.2% (18/26) | 84.6% (22/26) | 0.669 | 0.148 s |
| **Full hybrid + protected candidates + CrossEncoder** | **69.2% (18/26)** | **84.6% (22/26)** | **100.0% (26/26)** | **0.804** | **1.509 s** |

*Times are **approximate warm-query stage sums** calculated from shared work, not independently timed end-to-end calls. They exclude model initialization, API/UI/network time, and all LLM calls. Do not treat them as production latency benchmarks.*

### Retrieval strategies

1. **E5 only:** embed the question and rank document chunks by pgvector similarity.
2. **Hybrid RRF:** combine E5 semantic results, original lexical search, and Stanza-expanded lexical search using reciprocal rank fusion (`RRF_K = 20`). No CrossEncoder is applied.
3. **Full hybrid:** use the same three retrieval branches and RRF, preserve strong candidates from each branch (semantic top 5, original lexical top 2, Stanza lexical top 5), fill to a maximum of 16 unique candidates, then rerank using the CrossEncoder.

Each retrieval branch fetches up to 20 initial candidates. The comparison evaluates the first 10 ranked results for each strategy; Hit@5 is therefore directly comparable across variants.

### Interpretation

Compared with E5-only, the **full hybrid pipeline** improved:

- **Hit@1:** 57.7% → 69.2% (**+3 questions; +11.5 percentage points**).
- **Hit@3:** 69.2% → 84.6% (**+4 questions; +15.4 percentage points**).
- **Hit@5:** 80.8% → 100.0% (**+5 questions; +19.2 percentage points**).
- **MRR@10:** 0.664 → 0.804 (**+0.140**).

RRF without reranking improved Hit@5 by only one question relative to E5-only, with no Hit@1 or Hit@3 change. The large gain appears only in the **combined protected-candidate + CrossEncoder stage**. This comparison does **not** isolate how much of that gain comes from candidate protection versus the CrossEncoder itself; that would require an additional ablation.

The full strategy also has the highest estimated retrieval cost. In an insurance assistant, better clause retrieval can justify additional latency, but the trade-off should be validated on a larger test set and with independent latency measurements.

## Performance context

A separate, earlier **single observed retrieval execution** recorded:

| Stage | Observed latency |
| --- | ---: |
| Embedding | 0.020 s |
| Semantic search | 0.007 s |
| Original lexical search | 0.031 s |
| Stanza processing | 0.032 s |
| Stanza lexical search | 0.026 s |
| CrossEncoder reranker | 1.196 s |
| **Total retrieval** | **1.315 s** |

This is **one earlier observation**, not the mean of the comparison run and not a measure of the complete chat request. The comparison's **1.509 s** full-pipeline figure is a separate, stage-derived mean across 26 questions.

## Reproduce the comparison

Run from `server/`, with the seeded PostgreSQL database and indexed insurance document available:

```powershell
python -m scripts.compare_retrieval --check
python -m scripts.compare_retrieval --output data/evals/runs/retrieval-comparison.json
```

If multiple ready product versions contain the same document, supply `--product-version-id <UUID>` to select one explicitly. The comparison script uses a read-only transaction and does not call the external LLM provider.

The local JSON report includes per-case ranks, aggregate metrics, stage timings, dataset hash, and the Git commit SHA when available. Preserve that report with the experiment records; the summary above reflects the reported local run rather than a fresh reproduction performed for this document.

## Limitations and next experiments

- Only **26 questions from one document** are evaluated. The 100% Hit@5 result is limited to that dataset and is **not** a production reliability guarantee.
- Ground truth is **article-level**, not exact clause-level. A retrieved article might omit conditions or exceptions needed for a safe answer.
- Retrieval quality is **not** answer correctness, policy applicability correctness, or Model B validation quality.
- The current comparison evaluates three combined strategies; to isolate contributions, add a **protected-candidate/no-reranker** ablation and a wider multilingual, adversarial dataset.
- Timing estimates share work across variants and exclude cold starts. For latency claims, measure each strategy independently over repeated warm runs and report median/p95.
- Independently review reference labels and expand coverage to more products, policy versions, and conditions requiring multiple clauses.
