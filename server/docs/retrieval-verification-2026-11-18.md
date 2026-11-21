# Step 1: heading-aware retrieval verification

Verified checkout `997ebb6` on 2026-11-18. Result: **does not pass retrieval
acceptance**. No application behavior was changed during this verification.

The backend regression suite completed with **83 passed**. The existing seeded
PostgreSQL integration test was excluded from pytest. Separately, the actual
retrieval pipeline was executed in a read-only PostgreSQL transaction, without
LLM calls, on 33 queries: the 26 retrieval reference cases, three original English
chat questions, and four actual translated planner queries from the prior chat run.

## Existing reference cases

Both compared reports resolve the same document and product version:
`f9d5a017-5ef8-445b-836c-3c9a8d3d7711` /
`3db4b1da-e92a-43d6-bc11-4ed5ba2b21e0`.

| Metric on the 26 reference cases | Before headings | Current headings |
| --- | --- | --- |
| Expected article at rank 1 | 18 / 26 | 18 / 26 |
| Expected article within top 3 | 23 / 26 | 22 / 26 |
| Expected article within top 5 | 26 / 26 | 25 / 26 |
| Mean reciprocal rank in returned top five | 0.8109 | 0.7897 |

The damaged-baggage repair case regressed: article 38 previously ranked first
but is now absent from the final results. It still appears at semantic rank 15
and expanded lexical rank 9, then disappears from the 12 reranker candidates.
Previously its expanded lexical rank was 5, which protected it from removal.

Other changes: lost-passport assistance moved 4 to 5; prescribed medicines moved
1 to 3; passport exclusion improved 2 to 1; visa cancellation improved 3 to 1.
The unchanged hit-at-one count therefore hides a meaningful regression.

## Actual planner-query checks

| Query | Expected article | Current final rank |
| --- | --- | --- |
| Theft reporting procedure | 37 | Missing |
| Passport baggage exclusion | 39 | 1 |
| Baggage-delay eligibility | 44 | 1 |
| Baggage-delay receipts/documents | 44 | 2 |

The theft query is:
`Jaký je postup při nahlášení krádeže zavazadel v zahraničí a jaké dokumenty jsou potřeba?`
Article 37 is absent from all three initial top-20 retriever lists. The heading
change has not fixed this miss; reranking alone cannot recover an absent candidate.

Original English questions were also diagnosed directly, bypassing the planner.
The theft and passport originals still miss their articles; these direct calls
must not be confused with the application's translated-query path above.

## Next narrow step

Investigate the theft clause's initial retrieval scores and preserve the prior
body-only lexical signal when adding heading information, so the repair clause
is not displaced. Repeat this retrieval check before another end-to-end LLM run.
Final-answer correctness and paraphrase evaluation are separate later steps.

Local Git-ignored reports:

- Before: `data/evals/runs/retrieval-stages-before.json`
- Current: `data/evals/runs/step1-retrieval-verification-2026-11-18.json`

Reproduction from `server`:

```powershell
python -m scripts.diagnose_retrieval --chat-report data/evals/runs/after-runtime-fixes-database.json --output data/evals/runs/step1-retrieval-new-run.json
```
