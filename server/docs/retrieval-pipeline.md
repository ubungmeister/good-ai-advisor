# Retrieval Pipeline — Design, Experiments, and Current Setup

## 1. Goal

This document records how the retrieval part of the insurance AI advisor evolved, why each component exists, what performance problems were found, and what the current architecture is.

The main purpose is to preserve the reasoning so the same approach can be reused in future RAG projects.

## 2. What RAG means here

RAG is the whole flow:

```text
User question
    ↓
Retrieve relevant knowledge
    ↓
Give retrieved knowledge to the LLM
    ↓
Generate an answer
```

In our project:

```text
E5 + pgvector       = semantic/vector retrieval
PostgreSQL pg_trgm  = lexical retrieval
Cross-encoder       = reranking
RRF                 = rank fusion
All of them + LLM   = RAG pipeline
```

## 3. Knowledge source

The first real source is the travel insurance terms:

```text
VPP CP 2021
Všeobecné pojistné podmínky – Cestovní pojištění
Effective from 2021-04-01
```

Current ingestion result:

```text
KnowledgeDocument: VPP_CP_2021
Chunks:             124
Maximum chunk size: 400 tokens
Embedding size:     384 dimensions
```

Chunks do not cross article boundaries. Metadata includes document code, part/article information, source pages, chunk index and token count.

## 4. First retrieval version

Initial architecture:

```text
Question
   ↓
E5 embedding
   ↓
pgvector cosine search
   ↓
Top K chunks
```

Embedding model:

```text
intfloat/multilingual-e5-small
384 dimensions
normalized embeddings
```

E5 uses:

```text
query:   <question>
passage: <document chunk>
```

Document embeddings are created during ingestion and stored in PostgreSQL. At runtime only the user question needs to be embedded.

Typical measured latency:

```text
Embedding:      ~0.02–0.05 s
Vector search:  ~0.05 s
```

So pgvector itself was not the bottleneck.

## 5. Why vector search alone was not enough

The retrieval eval included cases such as:

```text
baggage theft                → Article 35
baggage delay                → Article 44
liability/property damage    → Article 21
find a doctor                → Article 14
lost passport                → Article 14
vaccination information      → Article 15
```

Problematic example:

```text
Question:
Co když během cesty poškodím cizí věc?

Expected:
Article 21
```

With E5-only retrieval, Article 21 was around rank #29.

The chunk existed in the DB and had a valid embedding. The problem was ranking, not ingestion.

Lesson:

> Semantic retrieval can understand the topic but still rank the exact legal/insurance clause too low.

## 6. Adding a reranker

Architecture became:

```text
Question
   ↓
E5 retrieval
   ↓
Top 40 candidates
   ↓
Cross-encoder reranker
   ↓
Top results
```

E5 works independently:

```text
question → vector
chunk    → stored vector
vector ↔ vector
```

A cross-encoder is more expensive:

```text
question + chunk #1 → Transformer
question + chunk #2 → Transformer
...
question + chunk #40 → Transformer
```

It can judge relevance better because it reads the question and passage together, but inference cost grows with candidate count.

## 7. First reranker: BGE

Model tested:

```text
BAAI/bge-reranker-v2-m3
```

Quality improvement was real:

```text
Article 21:
E5 rank ~29
BGE reranker rank #1
```

But CPU latency was unacceptable.

PyTorch benchmark:

```text
~26.78 s
```

## 8. ONNX + INT8 optimization

We then optimized inference:

```text
PyTorch FP32
    ↓
ONNX Runtime
    ↓
INT8 quantization
```

For BGE:

```text
~26.78 s → ~15.63 s
```

This was faster, but still too slow for a real-time chat.

Lesson:

> ONNX and INT8 can help a lot, but they do not automatically make a very large model suitable for low-latency CPU inference.

## 9. Smaller reranker

We tested:

```text
cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
```

Why:

```text
smaller model
multilingual
Apache-2.0
ONNX exports available
lower inference cost
```

Measured warm latency:

```text
PyTorch:          ~4.06 s
ONNX INT8:        ~2.17–2.36 s
```

Initialization took around 15–20 seconds, but initialization is a startup cost, not request latency, if the model is loaded once and reused.

## 10. Profiling proved the bottleneck

We instrumented RetrievalService using `time.perf_counter()`.

Warm request:

```text
Embedding:       0.049 s
Vector search:   0.054 s
Reranker:        2.260 s
Hybrid ranking:  ~0 s
TOTAL:           2.364 s
```

This proved:

```text
E5            ✅ fast
PostgreSQL    ✅ fast
RRF           ✅ negligible
Reranker      ❌ bottleneck
```

Lesson:

> Measure each stage before optimizing. Do not guess.

## 11. Why simply reducing Top K was dangerous

The obvious optimization would have been:

```text
32 candidates → 12 candidates
```

But Article 21 was around E5 rank #29.

So E5 Top 12 would remove the correct chunk before the reranker ever saw it.

That would improve latency by destroying recall.

We needed to improve candidate generation first.

## 12. Lexical retrieval

We added a second retrieval method in PostgreSQL:

```text
pg_trgm
unaccent
word_similarity(...)
```

Semantic search asks roughly:

```text
"What text means something similar?"
```

Lexical search asks roughly:

```text
"What text contains similar words or word fragments?"
```

Example:

```text
Question:
poškodím cizí věc

Article 21:
poškozením ...
věci ...
způsobil jinému ...
```

`pg_trgm` compares character trigrams, so related forms such as:

```text
poškodím
poškozením
```

can still match well.

`unaccent` helps normalize Czech diacritics.

Result for the problematic query:

```text
Article 21

E5:
~rank #29

Lexical:
rank #1
```

This was the key improvement.

## 13. Current hybrid candidate retrieval

Current pipeline:

```text
                    Question
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
       Semantic search      Lexical search
       E5 + pgvector        pg_trgm
          Top 20             Top 20
              ↓                 ↓
              └────────┬────────┘
                       ↓
                   RRF fusion
                       ↓
                  Top 12
                       ↓
              MiniLM ONNX INT8
                       ↓
                  Final Top 5
```

This is hybrid retrieval.

Important distinction:

Previous experiment:

```text
E5 ranking + reranker ranking
```

Current design:

```text
semantic retrieval + lexical retrieval
        ↓
RRF candidate fusion
        ↓
reranker
        ↓
final ranking
```

The current design is cleaner because retrieval finds candidates and the reranker produces the final ordering.

## 14. Why RRF is used

Semantic and lexical scores use different scales, so raw scores should not simply be added.

Instead we combine ranks.

Reciprocal Rank Fusion:

```text
RRF score =
1 / (k + semantic_rank)
+
1 / (k + lexical_rank)
```

Current:

```text
k = 20
```

The point is that both retrieval systems contribute without requiring their raw score scales to be calibrated.

## 15. Current performance

After semantic + lexical retrieval and reducing reranker candidates to 12:

```text
Embedding:         ~0.024 s
Semantic search:   ~0.047 s
Lexical search:    ~0.025 s
RRF fusion:        ~0.000 s
Reranker:          ~0.670 s
TOTAL retrieval:   ~0.767 s
```

Historical comparison:

```text
BGE PyTorch:                         ~26.78 s
BGE ONNX INT8:                       ~15.63 s
MiniLM ONNX INT8 with 32 candidates: ~2.36 s
Current hybrid + 12 candidates:      ~0.77 s
```

The Article 21 case also improved to final rank #1.

## 16. Current evaluation

Six-query evaluation:

```text
baggage_theft
expected Article 35
rank 2

baggage_delay
expected Article 44
rank 1

liability_property_damage
expected Article 21
rank 1

assistance_find_doctor
expected Article 14
rank 5

assistance_lost_passport
expected Article 14
rank 3

assistance_vaccination_info
expected Article 15
rank 7
```

Metrics:

```text
Hit@1: 33.33%
Hit@3: 66.67%
Hit@5: 83.33%
MRR:   0.529
```

This eval is still too small for production conclusions.

Do not aggressively tune the pipeline around only these six questions.

## 17. Current components

### Embedding

```text
Model:          intfloat/multilingual-e5-small
Dimensions:     384
Normalization:  enabled
```

### Semantic search

```text
PostgreSQL
pgvector
cosine distance
```

### Lexical search

```text
PostgreSQL
pg_trgm
unaccent
word_similarity
```

### Reranker

```text
cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
ONNX Runtime
INT8
12 candidates
```

### Fusion

```text
semantic Top 20
lexical Top 20
RRF k = 20
final candidate count = 12
```

## 18. Current request lifecycle

```text
User question
      ↓
EmbeddingService.embed_query()
      ↓
┌─────────────────────────────────────┐
│ DocumentChunkRepository             │
│                                     │
│ search_similar()                    │
│   E5 + pgvector                     │
│                                     │
│ search_lexical()                    │
│   pg_trgm + unaccent                │
└─────────────────────────────────────┘
      ↓
RetrievalService._fuse_retrieval_results()
      ↓
Top 12 candidates
      ↓
RerankerService.rerank()
      ↓
Top 5 chunks
      ↓
Future ContextBuilder
      ↓
Future LLM
```

## 19. Why the reranker is still useful

Semantic + lexical retrieval is mainly for recall: find good candidates.

The reranker is for precision: decide which of those candidates best answers the specific question.

Example:

```text
Question:
I damaged someone else's property.

Candidate A:
My baggage was damaged.

Candidate B:
I caused damage to another person's property.
```

Both may contain related vocabulary.

The cross-encoder sees `question + candidate` together and can make a better relevance decision.

Responsibilities:

```text
Semantic + lexical → candidate recall
Reranker           → final precision
```

## 20. Initialization vs request latency

Do not confuse:

```text
model initialization
```

with:

```text
request inference
```

Observed:

```text
Service initialization: ~15–20 s
Warm retrieval request: ~0.77 s
```

Production should behave like:

```text
container starts
↓
load E5 once
load reranker once
↓
health check becomes READY
↓
reuse those instances for many requests
```

Never load the model inside each chat request.

Bad conceptually:

```python
@router.post("/chat")
def chat(...):
    retrieval_service = RetrievalService()
```

Better:

```text
application startup
↓
create RetrievalService once
↓
reuse it
```

This should be verified when the real chat endpoint is implemented.

## 21. Why OpenSearch is not needed yet

We considered using OpenSearch because it can provide:

```text
lexical search
vector search
hybrid retrieval
rank fusion
reranking integrations
```

and can be self-hosted inside company infrastructure.

But the current PostgreSQL solution now has:

```text
sub-second retrieval
simple deployment
no extra search cluster
reasonable early eval results
```

Current strategy:

```text
keep PostgreSQL hybrid retrieval
↓
expand eval dataset
↓
measure quality
↓
introduce OpenSearch only if there is a demonstrated need
```

## 22. Enterprise/security direction

The retrieval stack should be deployable without sending insurance data to a public external search or reranking API.

Possible self-hosted architecture:

```text
Private company network / VPC

Frontend
   ↓
FastAPI
   ├── PostgreSQL
   ├── pgvector
   ├── local embedding model
   ├── local reranker
   └── private/internal LLM
```

Keep abstractions such as:

```text
EmbeddingService
RetrievalService
RerankerService
```

so implementations can be replaced later without rewriting business logic.

## 23. Main lessons

1. Vector search alone is often not enough for legal/insurance documents.
2. Lexical retrieval is valuable because exact terminology matters.
3. Cross-encoder rerankers improve precision but are expensive.
4. Candidate count strongly affects reranker latency.
5. Never reduce candidate count before checking recall.
6. ONNX and INT8 can significantly reduce CPU inference cost.
7. Measure each stage before optimizing.
8. Build a retrieval eval before tuning.
9. Do not overfit to six questions.
10. Specialized search engines such as OpenSearch are an option, not a default requirement.

## 24. Next step

Expand the retrieval evaluation from 6 cases to roughly 20–30 realistic insurance questions across:

```text
baggage
medical expenses
liability
assistance
cancellation
sports
exclusions
travel documents
delays
territory
claim situations
```

Then measure:

```text
Hit@1
Hit@3
Hit@5
MRR
latency
```

Only after that decide whether PostgreSQL hybrid retrieval is sufficient or whether OpenSearch is justified.

## 25. Current baseline architecture

```text
                         USER QUESTION
                              │
                              ▼
                       RetrievalService
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
          EmbeddingService        Lexical retrieval
           multilingual E5          PostgreSQL
                  │                  pg_trgm
                  ▼                       │
             pgvector                    │
                  │                       │
                  └───────────┬───────────┘
                              ▼
                         RRF fusion
                              │
                         Top 12 chunks
                              │
                              ▼
                       RerankerService
                       MiniLM ONNX INT8
                              │
                              ▼
                          Top 5 chunks
                              │
                              ▼
                    Future ContextBuilder
                              │
                              ▼
                             LLM
```

This is the current retrieval baseline to preserve before making further changes.
