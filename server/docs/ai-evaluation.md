# AI evaluation baseline

Audit item 3.4 adds a small benchmark beyond article retrieval scores. The
versioned dataset is `data/evals/ai_eval.json`: 10 chat scenarios and 12 labeled
validator drafts. Labels were checked against the synthetic policy and the
included structured VPP source; independent human review is still required.
The first run and its failures are recorded in [the baseline findings](ai-evaluation-baseline.md).

## What runs

Chat cases execute the real ChatService safety classifier, planner, task routing,
context construction, generator, validator and regeneration/fallback policy.
The policy is synthetic: baggage limit 100,000 CZK, premium 1,290 CZK, PAID,
dates 2026-09-01 to 2026-09-15, no supplied deductible or payment date.
Conversations, messages, source persistence and AI-run persistence stay in memory.
No user or policy IDs from `.env` are used. HTTP, authentication and persistence
are outside this benchmark.

Two retrieval modes must be interpreted separately:

- `fixture` (default) supplies the specified complete source articles. This is an
  oracle-evidence experiment that isolates downstream AI behavior, not an
  end-to-end retrieval result. No database or embedding/reranking models are needed.
- `database` uses the real retrieval pipeline and a resolved READY embedded
  VPP_CP_2021 product version in a PostgreSQL READ ONLY transaction. It evaluates
  retrieval through final answer, with the same synthetic policy and memory
  persistence. All documents under that product version remain eligible, matching
  application retrieval scope. Inspect evidence document IDs during review.

Validator cases bypass generation and run real ResponseValidator/Model B on
fixed labeled drafts. They include correct facts, wrong amounts/dates, invented
deductibles, mixed supported/unsupported claims, a reversed exclusion, no
evidence, an empty draft and a still-wrong retry. Their evidence is controlled in
both retrieval modes so the reference label cannot change with a retrieval miss.

## Commands

From `server`, using the configured project Python environment:

```powershell
# Offline input checks; no provider calls, model downloads or database access.
python -m scripts.run_ai_eval --check

# Real configured LLM calls with known evidence; writes only the report file.
python -m scripts.run_ai_eval --output data/evals/runs/fixture-baseline.json

# Full retrieval-to-answer experiment against the existing indexed database.
python -m scripts.run_ai_eval --suite chat --retrieval database --output data/evals/runs/database-baseline.json

# If the document is indexed under several versions, choose one explicitly.
python -m scripts.run_ai_eval --suite chat --retrieval database --product-version-id <UUID> --output data/evals/runs/database-version-baseline.json

# Measure the validator separately.
python -m scripts.run_ai_eval --suite validator --output data/evals/runs/validator-baseline.json
```

Inference uses the configured LLM provider and may incur API charges. Database
mode needs the existing ingestion and cached models, or their first downloads.
Each case has a 90-second default asyncio timeout (`--timeout` changes it).
Synchronous retrieval work cannot be interrupted by that asyncio deadline; this
runner is not a hard wall-clock watchdog. Cases execute
sequentially. Reports are saved after every case; an existing output path is
refused. A case exception produces an error row and a nonzero process exit,
not a passing fallback. Missing-policy scenarios can therefore expose existing
runtime errors instead of hiding them. Service failures and real quality failures
are reported separately. Runtime prints are suppressed during each case.

## Review and metrics

Open the JSON report, inspect each answer, rubric and captured evidence, and fill
the chat row's `review` fields:

```json
{"reviewer":"Your name", "correct":true, "grounded":true,
 "behavior_correct":true, "notes":"Checked amount and currency against policy evidence."}
```

Use `false` when any material required point is wrong or missing. An unsupported
extra claim fails grounding even if the requested number is correct. A fallback
on an answerable question may be safe but fails answer correctness/availability.
For clarification/handoff cases, judge whether that behavior is appropriate and
avoids fabricated facts; don't require a numeric answer. Execution errors remain
errors rather than reviewable successes. Leave uncertain reviews unset and explain
why in notes. Prefer an independent reviewer, especially before publishing scores.

```powershell
python -m scripts.run_ai_eval --summarize data/evals/runs/fixture-baseline.json
```

- Validator **false accepts**: invalid labeled drafts released as OK.
- **Blocked valid**: valid drafts not released, including fail-closed outages;
  `service_failures` distinguishes validator infrastructure failures.
- **Label accuracy across all cases** counts decision matches, but gives no
  credit for service failures or execution errors. It is acceptance-decision
  accuracy, not a claim that Model B diagnosed the exact grounding error.
- Chat **route matches** are a diagnostic count, not an answer-quality score.
  Correctness, grounding and behavior rates remain null until a named reviewer
  fills all three booleans. Always report reviewed/total coverage with these rates.

Reports contain real answers, validation drafts, trusted evidence, per-case
latency, provider/model, dataset/source/policy/runtime/harness hashes and Git commit.
The `complete` flag remains false until every selected case has been attempted;
completion does not mean that every case passed. Preserve
reports and run parameters when comparing a change; never compare fixture and
database results as if their evidence were identical. Provider outputs are not
deterministic, so repeat important comparisons. Do not tune and claim general
accuracy on this same small development set; add independently labeled held-out
cases, more policies/documents and Czech paraphrases before broader claims.

Generated runs are Git-ignored. Keep synthetic inputs: this evaluator is not
intended to export real customer policy data into model calls or reports.
