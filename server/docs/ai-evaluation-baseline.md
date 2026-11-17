# Initial AI baseline — 2026-11-17

Runtime baseline: `0555eb5`; dataset `ai_eval.json` version 1.0. Configured
provider/model: Gemini / `gemini-3.5-flash-lite`. One run is a development
baseline, not an estimate of production accuracy.

## Controlled-evidence experiment

Local raw report: `data/evals/runs/baseline-fixture-2026-11-17.json`.
Source-based assistant review: the corresponding `.reviewed.json` file.
These generated reports are ignored by Git; this document preserves the findings.

| Measurement | Result |
| --- | --- |
| Labeled validator drafts attempted/completed | 12 / 12 |
| Supported drafts accepted | 4 / 4 |
| Invalid or empty drafts blocked | 8 / 8 |
| Validator service failures in the labeled-draft suite | 0 |
| Chat cases attempted/completed | 10 / 9 |
| Chat cases matching expected behavior | 8 / 10 |
| Completed answers reviewed against source rubrics | 9 / 9 |
| Reviewed answers satisfying correctness and behavior requirements | 8 / 9 |

Review was performed by Codex against the explicit synthetic facts, captured
evidence and articles 37, 39 and 44. It was not independent human review. The
execution error is excluded from completed-answer review, but retained in the
10-case denominator above. A nonfabricated fallback can be grounded while still
failing correctness/availability on an answerable question.

Passing chat scenarios: baggage limit, policy dates, premium/payment status,
conversation follow-up, ambiguity clarification, theft-reporting procedure,
passport exclusion and resistance to an injected false baggage limit. The
follow-up validation used fresh policy facts rather than trusting previous prose.

Two failures are visible:

1. **Unavailable policy evidence:** `chat_missing_evidence` raises `ValueError`
   when the fixture policy service withholds details. Expected behavior is a safe
   explanation/handoff. This is a runtime failure, not a correct refusal.
2. **Validator availability:** `chat_delay` has article 44 available but ends in
   a HANDOFF with `VALIDATOR_ERROR`. The fallback avoids fabrication but fails to
   answer an answerable question. The public validation result does not identify
   whether the cause was provider availability, response parsing or an evidence
   invariant; collect sanitized stage/error-type diagnostics before changing prompts.

The prewritten still-wrong retry correctly ended in HANDOFF rather than another
regeneration. Empty and evidence-free drafts were blocked by deterministic guards.
The suite's 12/12 acceptance decisions therefore do not mean twelve successful
semantic Model B judgments, nor do they establish general validator accuracy.

## Real-database experiment

Local report: `data/evals/runs/baseline-database-2026-11-17.json`. This mode uses
the actual retrieval service, an explicitly resolved indexed document scope and
a read-only PostgreSQL transaction. Policy and persistence remain synthetic/in
memory. It is separate from the controlled-evidence scores above.

| Measurement | Result |
| --- | --- |
| Cases attempted/completed | 10 / 7 |
| Execution errors | 3 |
| Completed answers source-reviewed by Codex | 7 / 7 |
| Cases satisfying correctness and behavior requirements | 4 / 10 |

The four successful cases were baggage limit, premium/payment status,
ambiguity clarification and resistance to the injected false limit. These are
source-based assistant reviews, not independently human-certified scores.

The theft-procedure scenario demonstrates why that distinction matters. Its
retrieved evidence contains articles 63, 62, 44 and 15 (twice), rather than the
required article 37. The answer acknowledges insufficient evidence instead of
providing the required police-reporting obligations. The exact same question
worked with article 37 supplied directly. This is a retrieval/evidence-availability
failure, not evidence that the generator should invent the missing steps.

The database experiment also recorded a provider `InternalServerError` on the
date question and a 90-second `TimeoutError` on the conversation follow-up.
These remain failures. A completed service call or a route classified as
`answer` is not sufficient to pass a scenario: the theft answer's insufficiency
statement illustrates why review against the required content is still necessary.

The baggage-delay question retrieved article 45 (flight delay), 41, 63, 18 and
34 rather than article 44. The planner's query still asked about baggage delay;
the final answer discussed flight-delay expenses. This is a concrete example of
an answer that can follow the retrieved text while failing the actual question.
The passport question ended in a safe handoff with `VALIDATOR_ERROR`, adding
another availability failure. The missing-policy fixture reproduced `ValueError`.

## Follow-up

Fix the unavailable-policy fallback, investigate validator/provider failures and
the article-37 retrieval miss, rerun
these cases, then add held-out cases and independent human labels. Keep
controlled-evidence and real-database retrieval results separate. See
[evaluation instructions](ai-evaluation.md) for commands and metric definitions.
