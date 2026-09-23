# Retrieval Ranking Strategy

## Goal

The retrieval pipeline should:

1. Find potentially relevant chunks with high recall.
2. Rank the most relevant chunks near the top.
3. Avoid losing good results when the reranker makes a mistake.

Current pipeline:

User Question
    ↓
E5 Embedding
    ↓
Vector Search
    ↓
Top 40 candidates
    ↓
Cross-Encoder Reranker
    ↓
Hybrid Rank Fusion
    ↓
Final Top 5–10 chunks
    ↓
LLM

---

## Stage 1 — E5 Vector Search

E5 converts the question into an embedding.

Example:

Question:

"Co když během cesty poškodím cizí věc?"

E5 compares the query vector with all DocumentChunk embeddings
stored in PostgreSQL/pgvector.

It returns a broad candidate set:

#1  Article 62
#2  Article 70
...
#29 Article 21
...
#40 ...

The correct Article 21 was found, but its rank was too low.

E5 is therefore used mainly for:

- fast search
- high recall
- candidate generation

---

## Stage 2 — Reranker

The reranker receives the original question and every candidate text.

Unlike vector search, it evaluates the texts together:

Question + Chunk
    ↓
Cross Encoder
    ↓
Relevance score

Example:

E5:

Article 21 → rank 29

After reranking:

Article 21 → rank 1

The reranker is better at understanding detailed relationships between
the question and the candidate text.

However, reranking is not always correct.

Example:

Vaccination question:

E5:
Article 15 → rank 5

Reranker:
Article 15 → rank 11

Therefore blindly trusting the reranker can remove an already good
vector-search result.

---

## Stage 3 — Hybrid Ranking

Instead of trusting only E5 or only the reranker, both rankings are used.

For every candidate we have:

- E5 rank
- reranker rank

Example:

| Chunk | E5 Rank | Reranker Rank |
|---|---:|---:|
| Article 21 | 29 | 1 |
| Article 15 | 5 | 11 |

We calculate a new score using Weighted Reciprocal Rank Fusion.

Formula:

final_score =
    E5_WEIGHT / (RRF_K + e5_rank)
    +
    RERANKER_WEIGHT / (RRF_K + reranker_rank)

Current experimental values:

E5_WEIGHT = 0.3
RERANKER_WEIGHT = 0.7
RRF_K = 20

The reranker has more influence, but E5 still protects chunks that
performed well during initial retrieval.

---

## Example — Article 21

E5 rank:

29

Reranker rank:

1

Calculation:

0.3 / (20 + 29)
+
0.7 / (20 + 1)

=

0.3 / 49
+
0.7 / 21

≈

0.0061 + 0.0333

=

0.0394

Hybrid score:

0.0394

The strong reranker result compensates for the weak E5 rank.

---

## Example — Article 15

E5 rank:

5

Reranker rank:

11

Calculation:

0.3 / (20 + 5)
+
0.7 / (20 + 11)

=

0.3 / 25
+
0.7 / 31

≈

0.0120 + 0.0226

=

0.0346

Hybrid score:

0.0346

The strong E5 rank helps prevent the chunk from falling too far because
of the weaker reranker result.

---

## Final Sorting

Every candidate gets one hybrid score.

Example:

Chunk X     → 0.0441
Article 21  → 0.0394
Article 15  → 0.0346
Chunk Y     → 0.0318

We sort from highest score to lowest:

#1 Chunk X
#2 Article 21
#3 Article 15
#4 Chunk Y

Then only the best results are returned:

Top 40 candidates
    ↓
Hybrid ranking
    ↓
Top 5–10
    ↓
LLM context

---

## Why not combine raw model scores?

E5 and the reranker produce scores on different scales.

Example:

E5 cosine similarity:

0.8596

Reranker score:

7.42

These values are not directly comparable.

Doing:

0.8596 + 7.42

would have no meaningful interpretation.

Ranks are model-independent:

E5 rank = 5
Reranker rank = 11

Therefore rank fusion gives us a safer way to combine both systems.

---

## Important Principle

Vector search and reranking have different responsibilities.

E5:

"Find broadly relevant candidates."

Reranker:

"Read those candidates more carefully."

Hybrid ranking:

"Use both opinions before making the final decision."

The goal is:

high recall
+
good ranking
+
reasonable latency