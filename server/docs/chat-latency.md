# Interactive chat latency

The reported policy-overview request took 63.75 seconds and returned a handoff
after two validator timeouts. That request used policy records only, so the
retrieval candidate pool was not involved.

## Changes

- Gemini now uses one attempt by default, with a 20-second call budget. Fast-error
  retries can still be explicitly enabled, but share that same budget. Timeouts
  are never automatically retried. This is a per-provider-call budget, not a
  hard deadline for the entire HTTP request.
- Safety classification and read-only planning overlap. No retrieval or policy
  task is executed until the safety result permits normal flow. Critical flows,
  safety failures and cancellation discard and cancel pending planning work.
- A narrowly classified broad policy overview can use a template in English or
  Czech. Exactly one POLICY_DETAILS task with `policy_overview_language` is
  required, followed by exactly one ownership-checked PolicyTaskContent result.
  The template copies coverage names, limits/currencies and selected options.
  It does not invent missing fields, infer current coverage from ACTIVE status,
  or make event-coverage decisions. Its output is stored normally, with the
  answer source recorded as TEMPLATE / policy-overview-v1 in AI-run metadata.
- This template generates no LLM prose and therefore has no Model A/B calls.
  Specific questions, mixed tasks, other languages and coverage explanations
  continue through generation and grounding validation. Missing policy data
  still takes the safe unavailable-policy path.
- Generated answers default to concise wording without dropping material
  conditions. The validator uses the original canonical evidence IDs and
  applies the existing evidence-ID and verdict checks.
- LLM stage timings are printed on success and failure without prompt contents.

## Measurement

The benchmark uses the real configured safety/planning/answer/validator services
with an in-memory synthetic policy shaped like the reported request: four
coverages, three options, one policyholder role and travel details. It does not
query or update customer records. These are AI-flow measurements, not complete
HTTP or browser timings. Provider/model: Gemini / gemini-3.5-flash-lite.

Reducing output alone was insufficient: the first three runs took 54.63 seconds
(regenerated), 29.70 seconds (validated), and 40.51 seconds (generation timeout).

With the recorded-policy template and overlapping safety/planning:

| Run | Time | Result |
| --- | --- | --- |
| 1 | 8.81 s | Exact match to the factual fixture template |
| 2 | 9.21 s | Exact match to the factual fixture template |
| 3 | 8.53 s | Exact match to the factual fixture template |

Every run made two model calls; there were no generation, regeneration or
semantic-judge calls on this template path. The average was 8.85 seconds.
The remaining latency was safety/planning provider time. Three runs are a small
sample, not a production latency guarantee or a general RAG benchmark.

From `server`:

```powershell
python -m scripts.benchmark_policy_overview --runs 3 --output data/evals/runs/policy-overview-new-run.json
python -m scripts.run_ai_eval --suite validator --output data/evals/runs/validator-new-run.json
```

Reports are preserved under Git-ignored `data/evals/runs/`. The measured local
reports are `policy-overview-latency-after.json` (output-size changes alone),
`policy-overview-latency-fastpath.json` (template/concurrency) and
`validator-after-latency-fix.json` (generated-answer validator checks).

Before removing the optional diagnostic variants and short evidence labels,
112 automated tests passed (the separately configured seeded
two-version database integration test was excluded). After their removal,
107 tests passed; the five tests specific to short labels were removed with
that feature. The same seeded integration test remained excluded.
In the earlier 12-case live
validator run, all eight invalid-answer cases were blocked and three of four
valid cases were accepted. The remaining valid procedure answer hit the
20-second provider timeout and was withheld: 11/12 expected outcomes, one
service failure, zero false accepts in this small dataset. That timeout is
an availability failure, not a successful semantic judgment. The labels still
await independent human review.

Restart the API when not using automatic reload. Longer generated explanations
still require sequential generation and validation and can be slower than a
recorded-policy overview. Validator/provider availability remains a separate
measurement; do not credit a fail-closed timeout as a correct semantic judgment.
