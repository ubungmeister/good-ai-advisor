# ResponseValidator Architecture

## Status

**Proposed final architecture for T5.9 — ResponseValidator**

This document defines the runtime validation layer that sits between the final answer generator and the user.

The goal is not to make the LLM "perfect".

The goal is to ensure that an answer cannot leave the backend unless it is sufficiently supported by trusted insurance data and passes hard backend rules.

---

# 1. Position in the runtime

```text
USER MESSAGE
    ↓
ChatService
    ↓
SafetyRouter
    ↓
QueryPlanner
    ↓
TaskPrioritizer
    ↓
TaskRouter
    ↓
Services / Tools
    ├── PolicyService
    └── RetrievalService
    ↓
STRUCTURED TaskResult[]
    │
    ├──────────────────────────────┐
    │                              │
    ▼                              ▼
ContextBuilder              GroundingFactBuilder
    │                              │
    ▼                              ▼
LLM-friendly context         GroundingFact[]
    │                              │
    ▼                              │
LLMService / MODEL A               │
Answer Generator                   │
    │                              │
    ▼                              │
Draft Answer ──────────────────────┘
    │
    ▼
ResponseValidator
    ├── Deterministic Guards
    └── GroundingValidator / MODEL B
    ↓
OK / REGENERATE / REJECT / HANDOFF
    ↓
USER
```

The validator is the last protection layer before a generated answer is returned to the customer.

---

# 2. Core principle

```text
AI understands meaning.

Backend controls execution.

Trusted services provide facts.

Grounding checker verifies semantic support.

ResponseValidator decides whether the answer may leave the backend.
```

The current transport rule is:

```text
Services return structured trusted data
        ↓
ChatService wraps it in typed TaskResult[]
        ↓
ContextBuilder formats it for Model A
        +
GroundingFactBuilder formats it for Model B
```

Structured data stays structured until one of those boundary components explicitly converts it.

The validator must not become another business-logic layer.

It does not decide what insurance covers.

It verifies whether the generated answer is supported by trusted data that the backend already obtained.

---

# 3. What is trusted evidence?

The validator must validate against the same trusted service results that were used to generate the answer.

Our two primary evidence sources are:

```text
POLICY
    ↓
PolicyService
    ↓
customer-specific contract facts
```

and:

```text
RETRIEVAL
    ↓
RetrievalService
    ↓
official insurance documentation chunks
```

Examples of policy facts:

```text
policy.status = ACTIVE
policy.start_date = 2026-07-10
policy.end_date = 2026-09-15
winter_sports = SELECTED
medical_expenses_limit = 5,000,000 CZK
```

Examples of retrieval evidence:

```text
Document chunk A
Document chunk B
Document chunk C
```

These arrive at the runtime as **structured typed `TaskResult` objects**:

```text
TaskResult[]
│
├── TaskResult
│     task_type = ...
│     target = POLICY
│     content = PolicyTaskContent
│
└── TaskResult
      task_type = ...
      target = RETRIEVAL
      content = RetrievalTaskContent
```

The current transport contract is conceptually:

```python
class TaskResult(BaseModel):
    task_type: TaskType
    target: TaskTarget
    content: PolicyTaskContent | RetrievalTaskContent
```

`PolicyTaskContent` keeps customer contract data structured:

```text
PolicyTaskContent
├── policy
├── coverages[]
├── options[]
├── people[]
└── travel_details
```

`RetrievalTaskContent` keeps the retrieved chunks structured:

```text
RetrievalTaskContent
└── chunks[]
      ├── id
      ├── document_id
      ├── content
      ├── score
      ├── page_number
      ├── article_number
      ├── section_title
      └── coverage_code
```

This preserves facts, IDs and provenance until a component actually needs a text representation.

---

# 4. Current TaskResult transport design

`TaskResult[]` is the shared trusted transport between service execution and downstream AI components.

The services produce structured data:

```text
PolicyService
    ↓
Policy details / ORM-backed contract data

RetrievalService
    ↓
DocumentChunk + reranker score
```

`ChatService` wraps those results into typed task content:

```text
PolicyService result
    ↓
PolicyTaskContent
    ↓
TaskResult(target=POLICY)

RetrievalService result
    ↓
RetrievalTaskContent
    ↓
TaskResult(target=RETRIEVAL)
```

`ChatService` should **not** flatten these objects with `json.dumps()` or `"\n".join(...)` before storing them in `TaskResult`.

The same trusted `TaskResult[]` then has two consumers:

```text
                         TaskResult[]
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
          ContextBuilder           GroundingFactBuilder
                 │                         │
                 ▼                         ▼
       text context for Model A     evidence for Model B
```

This gives us one source of truth and avoids reconstructing structured information later.

## ContextBuilder responsibility

`ContextBuilder` converts the structured task results into an LLM-friendly text representation.

Example policy path:

```text
PolicyTaskContent
    ↓
ContextBuilder
    ↓
[POLICY FACTS]

Policy status: ACTIVE
End date: 2026-09-15

Coverages:
- Medical Expenses, limit: 5,000,000 CZK

Policy options:
- Winter Sports: selected
```

Example retrieval path:

```text
RetrievalTaskContent
    ↓
ContextBuilder
    ↓
[INSURANCE DOCUMENTATION]

[DOCUMENT 1]
Chunk ID: <uuid>
Page: 12
Article: 5
...
```

## GroundingFactBuilder responsibility

`GroundingFactBuilder` consumes the **same structured `TaskResult[]`**, but it prepares evidence for Model B and preserves source identity.

Example policy facts:

```text
PolicyTaskContent
    ↓
GroundingFactBuilder
    ↓

GroundingFact(
    id="policy.status",
    text="Policy status: ACTIVE"
)

GroundingFact(
    id="policy.end_date",
    text="Policy end date: 2026-09-15"
)
```

For objects that already have stable database IDs, use evidence IDs that preserve provenance:

```text
policy.coverage:<coverage_uuid>
policy.option:<option_uuid>
document.chunk:<chunk_uuid>
```

Example retrieval fact:

```text
RetrievedChunk(
    id=<chunk_uuid>,
    content="...",
)
    ↓
GroundingFact(
    id="document.chunk:<chunk_uuid>",
    text="..."
)
```

This later aligns naturally with `MessageSource`, because exact policy coverage / option / document chunk provenance is still available.

---

# 5. Important decision: do not re-parse the final answer manually

The main validation architecture should NOT rely on rebuilding structured values from free-form LLM text.

We do not want this:

```text
LLM answer
    ↓
regex
    ↓
find dates
    ↓
dateparser
    ↓
find money
    ↓
find status
    ↓
normalize everything
    ↓
compare
```

Why?

Because natural language has too many variants:

```text
15.9.2026
15 September 2026
15 сентября 2026
15. září 2026
until 15 September
from 15 September
5 mil. Kč
5 000 000 CZK
five million crowns
```

Building a parser for all of this would become a separate NLP subsystem and would still remain fragile.

Instead, semantic claims in the generated answer are checked against trusted evidence by a grounding checker.

---

# 6. Final ResponseValidator design

```text
                     Draft Answer
                          │
                          ▼
                  ResponseValidator
                          │
          ┌───────────────┴────────────────┐
          │                                │
          ▼                                ▼
 Deterministic Guards              GroundingValidator
        Python                          Model B
          │                                │
          │                        semantic support check
          │                                │
          └───────────────┬────────────────┘
                          ▼
                   Decision Logic
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
             OK       REGENERATE    HANDOFF
```

`REJECT` is also available for invalid runtime states that must never be released.

---

# 7. Deterministic Guards

Deterministic guards are rules that Python can evaluate with certainty.

They do not interpret natural-language meaning.

Examples:

```text
draft answer is empty?
trusted evidence exists?
required service result exists?
critical flow accidentally entered normal flow?
validator result schema is valid?
grounding score passes threshold?
regeneration count exceeded?
```

Possible implementation:

```python
if not draft_answer.strip():
    return REGENERATE

if not task_results:
    return HANDOFF

if regeneration_count >= 1:
    return HANDOFF

if grounding_score < MIN_GROUNDING_SCORE:
    return REGENERATE
```

The important idea is:

```text
deterministic guard
=
backend rule with a predictable result
```

It is not:

```text
"Does this Czech sentence semantically mean the same thing as this database value?"
```

That belongs to grounding validation.

---

# 8. Grounding validation

Grounding answers one question:

> Are the material factual claims in the generated answer supported by trusted evidence?

Example:

```text
TRUSTED FACT

policy.end_date = 2026-09-15
```

Generated answer:

```text
Your insurance ends on 15 September 2026.
```

The wording differs from the structured value, but the meaning is the same.

The grounding checker should return:

```text
SUPPORTED
```

Another example:

```text
TRUSTED FACT

policy.end_date = 2026-09-15
```

Generated answer:

```text
Your insurance ends on 15 October 2026.
```

Result:

```text
CONTRADICTED
```

Another example:

```text
TRUSTED DOCUMENTATION

No information about heli-skiing was retrieved.
```

Generated answer:

```text
Heli-skiing is fully covered.
```

Result:

```text
UNSUPPORTED
```

---

# 9. Grounding Model — Model B

The answer generator and grounding checker have different jobs.

```text
MODEL A
=
generate a useful customer-facing answer
```

```text
MODEL B
=
verify whether the answer is supported by trusted evidence
```

Model B must NOT answer the user's insurance question.

Its prompt should be conceptually similar to:

```text
You are a factual grounding validator.

Do not answer the user's question.

Check whether every material factual claim in DRAFT ANSWER
is supported by TRUSTED EVIDENCE.

Do not use outside knowledge.
Do not assume missing facts.

Return only the required structured result.
```

---

# 10. Does Model B need to be a different provider?

No.

The architectural requirement is:

```text
Generator
    ≠
Verifier responsibility
```

It does not necessarily mean:

```text
Provider A
    ≠
Provider B
```

A reasonable first production-like setup is:

```text
LLMService
    ├── generation_model
    └── grounding_model
```

They may come from the same provider.

Later we can benchmark:

```text
same model family
vs
different model
vs
different provider
```

and choose based on evaluation quality, latency and cost.

The provider should not be changed only for architectural appearance.

---

# 11. Grounding facts

Before Model B is called, the structured trusted `TaskResult[]` is converted into a smaller, predictable grounding payload.

The important point is that the builder works from **structured task content**, not from strings that must be parsed again.

Conceptually:

```text
TaskResult[]
    ↓
GroundingFactBuilder
    ↓
GroundingFact[]
```

For `POLICY`:

```text
TaskResult(
    target=POLICY,
    content=PolicyTaskContent(...)
)
    ↓
GroundingFactBuilder
```

can produce granular facts such as:

```text
GroundingFact(
    id="policy.status",
    text="Policy status: ACTIVE"
)

GroundingFact(
    id="policy.end_date",
    text="Policy end date: 2026-09-15"
)

GroundingFact(
    id="policy.option:<option_uuid>",
    text="Winter Sports option: selected"
)

GroundingFact(
    id="policy.coverage:<coverage_uuid>",
    text="Medical Expenses limit: 5,000,000 CZK"
)
```

For `RETRIEVAL`:

```text
TaskResult(
    target=RETRIEVAL,
    content=RetrievalTaskContent(
        chunks=[...]
    )
)
    ↓
GroundingFactBuilder
```

produces one fact per retrieved chunk:

```text
GroundingFact(
    id="document.chunk:<chunk_uuid>",
    text="<official insurance document text>"
)
```

The `GroundingFact.id` is important because Model B can later return exact evidence references:

```text
claim
    ↓
supported by
    ↓
[
  "policy.option:<uuid>",
  "document.chunk:<uuid>"
]
```

This gives Model B one predictable evidence format while preserving provenance from the original backend objects.

---

# 12. Grounding checker input

The semantic grounding checker should receive:

```text
user question
+
draft answer
+
trusted grounding facts
```

Example:

```text
QUESTION

When does my insurance expire?


DRAFT ANSWER

Your insurance expires on 15 September 2026.


TRUSTED FACTS

[policy.status]
Policy status: ACTIVE

[policy.end_date]
Policy end date: 2026-09-15
```

The model then checks the claims in the answer against the supplied evidence.

---

# 13. Grounding checker output

The grounding model should return structured output.

Recommended conceptual schema:

```python
class GroundingClaim(BaseModel):
    claim: str
    supported: bool
    evidence_ids: list[str]


class GroundingCheckResult(BaseModel):
    verdict: GroundingVerdict
    support_score: float | None
    claims: list[GroundingClaim]
```

Example:

```json
{
  "verdict": "SUPPORTED",
  "support_score": 0.97,
  "claims": [
    {
      "claim": "The policy ends on 15 September 2026.",
      "supported": true,
      "evidence_ids": [
        "policy.end_date"
      ]
    }
  ]
}
```

For an incorrect answer:

```json
{
  "verdict": "CONTRADICTED",
  "support_score": 0.15,
  "claims": [
    {
      "claim": "The policy ends on 15 October 2026.",
      "supported": false,
      "evidence_ids": [
        "policy.end_date"
      ]
    }
  ]
}
```

---

# 14. Grounding verdicts

```text
NOT_CHECKED
```

Semantic grounding was intentionally not executed.

Possible use:

```text
simple deterministic/system response
```

---

```text
SUPPORTED
```

The relevant factual claims are supported by trusted evidence.

---

```text
UNSUPPORTED
```

The answer contains a material factual claim that is not established by the supplied evidence.

Example:

```text
"Heli-skiing is covered."
```

but no trusted source says that.

---

```text
CONTRADICTED
```

Trusted evidence explicitly conflicts with the generated claim.

Example:

```text
Trusted:
end_date = 2026-09-15

Generated:
end date = 2026-10-15
```

---

# 15. Validation actions

Grounding verdict and backend action are different concepts.

```text
GROUNDING VERDICT
=
what did validation discover?
```

```text
VALIDATION ACTION
=
what should ChatService do next?
```

Possible actions:

```text
OK
REGENERATE
REJECT
HANDOFF
```

## OK

The answer may be returned to the customer.

```text
SUPPORTED
    ↓
hard guards passed
    ↓
OK
```

## REGENERATE

The answer contains a recoverable generation error.

Example:

```text
UNSUPPORTED
or
CONTRADICTED
    ↓
first generation attempt
    ↓
REGENERATE
```

## HANDOFF

The system cannot safely produce a grounded answer.

Examples:

```text
required evidence is missing
```

or:

```text
second generated answer still fails validation
```

## REJECT

The answer must not leave the runtime because a hard invariant was violated.

This is mainly for system-level invalid states.

---

# 16. Only one regeneration attempt

The validator must never create an uncontrolled loop.

Approved behavior:

```text
Model A
    ↓
Draft #1
    ↓
ResponseValidator
    ↓
FAIL
    ↓
Regenerate once
    ↓
Draft #2
    ↓
ResponseValidator
    ↓
    ├── PASS → OK
    │
    └── FAIL → HANDOFF / safe fallback
```

Backend rule:

```python
MAX_REGENERATION_ATTEMPTS = 1
```

---

# 17. Regeneration feedback

If the first answer fails, Model A should receive specific validator feedback.

Example:

```text
Previous answer:

"Your policy expires on 15 October 2026."

Validation failure:

The statement about the policy end date contradicts trusted evidence.

Trusted evidence:

Policy end date: 2026-09-15

Generate a corrected answer using only the supplied evidence.
```

This is better than blindly calling the generator again with the same prompt.

---

# 18. Complexity-aware validation

Not every response needs the same validation cost.

Possible future routing:

```text
simple operational/system response
    ↓
deterministic guards
    ↓
OK
```

versus:

```text
coverage question
exclusion question
claim procedure
customer-specific policy + document reasoning
    ↓
deterministic guards
    +
grounding check
    ↓
OK / REGENERATE
```

The initial implementation may validate all normal generated insurance answers semantically.

Optimization can come later after we measure cost and latency.

Correctness comes first.

---

# 19. ResponseValidator responsibility

The validator SHOULD:

```text
- verify required trusted evidence exists
- run deterministic runtime guards
- run semantic grounding when required
- convert grounding result into backend action
- allow at most one regeneration
- trigger safe fallback / handoff after repeated failure
- expose validation issues for telemetry
```

The validator SHOULD NOT:

```text
- retrieve new insurance documents
- query policy data itself
- decide insurance coverage from scratch
- modify database facts
- generate the original customer answer
- invent missing evidence
- use outside knowledge to "fix" an answer
```

---

# 20. Proposed components

```text
Trusted TaskResult[]
        │
        └── GroundingFactBuilder
                │
                ▼
          GroundingFact[]

ResponseValidator
│
├── DeterministicGuardService
│
├── GroundingValidator
│      └── Model B
│
└── ValidationDecisionPolicy
```

Their responsibilities:

```text
DeterministicGuardService
=
hard backend checks
```

```text
GroundingFactBuilder
=
TaskResult[] → GroundingFact[]
```

```text
GroundingValidator
=
semantic claim-to-evidence validation
```

```text
ValidationDecisionPolicy
=
grounding result + guard result
→ OK / REGENERATE / REJECT / HANDOFF
```

We do not need to physically split all four into separate files immediately.

They describe responsibilities.

Implementation can start small and be extracted later when the code grows.

---

# 21. Proposed schemas

Existing high-level validation contract:

```python
class ValidationAction(StrEnum):
    OK = "OK"
    REGENERATE = "REGENERATE"
    REJECT = "REJECT"
    HANDOFF = "HANDOFF"


class GroundingVerdict(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
```

Current task-result transport schemas:

```python
class PolicyTaskContent(PolicyDetailsResponse):
    pass


class RetrievedChunk(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    score: float
    page_number: int | None = None
    article_number: str | None = None
    section_title: str | None = None
    coverage_code: str | None = None


class RetrievalTaskContent(BaseModel):
    chunks: list[RetrievedChunk]


class TaskResult(BaseModel):
    task_type: TaskType
    target: TaskTarget
    content: PolicyTaskContent | RetrievalTaskContent
```

The `target` and `content` type must agree:

```text
POLICY
    → PolicyTaskContent

RETRIEVAL
    → RetrievalTaskContent
```

This typed transport is used by both `ContextBuilder` and `GroundingFactBuilder`.

Recommended grounding-specific structures:

```python
class GroundingFact(BaseModel):
    id: str
    text: str


class GroundingClaim(BaseModel):
    claim: str
    supported: bool
    evidence_ids: list[str]


class GroundingCheckResult(BaseModel):
    verdict: GroundingVerdict
    support_score: float | None = None
    claims: list[GroundingClaim]
```

High-level result:

```python
class ValidationResult(BaseModel):
    action: ValidationAction
    grounding: GroundingVerdict
    issues: list[ValidationIssue]
```

The detailed grounding result may later be attached to `ValidationResult` or stored in `AiRun` telemetry.

---

# 22. Example — policy date

```text
USER
"When does my insurance expire?"

        ↓

PolicyService

        ↓

PolicyTaskContent
policy.end_date = 2026-09-15

        ↓

TaskResult(target=POLICY)
        │
        ├─────────────────────┐
        │                     │
        ▼                     ▼
ContextBuilder        GroundingFactBuilder
        │                     │
        ▼                     ▼
Model A context       GroundingFact(
        │                 id="policy.end_date",
        ▼                 text="Policy end date: 2026-09-15"
Model A              )
        │                     │
        ▼                     │
"Your insurance expires on   │
15 September 2026."           │
        │                     │
        └──────────┬──────────┘
                   ▼
          GroundingValidator
                Model B
                   │
                   ▼
               SUPPORTED
                   │
                   ▼
                  OK
```

No regex/dateparser is required. The validator receives the trusted structured policy value through `TaskResult` and Model B checks the natural-language claim against the derived grounding fact.

---

# 23. Example — coverage question

```text
USER
"Am I covered for skiing?"

        ↓

QueryPlanner

        ↓

COVERAGE_CHECK

        ↓

TaskRouter

        ↓

POLICY + RETRIEVAL
        │
        ├──────────────────────────┐
        ▼                          ▼
PolicyService               RetrievalService
        │                          │
        ▼                          ▼
PolicyTaskContent          RetrievalTaskContent
        │                          │
        └────────────┬─────────────┘
                     ▼
                TaskResult[]
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   ContextBuilder       GroundingFactBuilder
          │                     │
          ▼                     ▼
   Model A context       GroundingFact[]
          │                     │
          ▼                     │
       Model A                  │
          │                     │
          ▼                     │
    Draft answer ───────────────┘
                     │
                     ▼
             GroundingValidator
                  Model B
                     │
                     ▼
       claim-by-claim support check
                     │
                     ▼
SUPPORTED / UNSUPPORTED / CONTRADICTED
```

Example structured policy evidence may include:

```text
policy_status = ACTIVE
option WINTER_SPORTS = selected
sport_level = RECREATIONAL
```

Retrieval evidence remains individual chunks with their original IDs and metadata. Model B can therefore cite both the selected policy option and the exact insurance-document chunk supporting the coverage explanation.

This is where semantic grounding is especially important.

---

# 24. Example — unsupported hallucination

Trusted evidence:

```text
No retrieved source establishes heli-skiing coverage.
```

Generated answer:

```text
"Heli-skiing is fully covered by your policy."
```

Validator:

```text
GroundingVerdict.UNSUPPORTED
```

Decision:

```text
first attempt
    ↓
REGENERATE
```

If the regenerated answer still fails:

```text
HANDOFF
```

---

# 25. Observability

Validation information should later be persisted in `AiRun`.

Useful telemetry:

```text
grounding_verdict
grounding_score
validation_action
validation_issue_codes
regeneration_count
validator_model
validator_latency_ms
```

This lets us measure:

```text
How often does Model A hallucinate?

Which tasks fail grounding most often?

How often does regeneration fix the answer?

How much latency does validation add?

Does Model B reject valid answers too often?
```

These measurements will determine later optimizations.

---

# 26. Testing strategy

The validator needs its own regression dataset.

Minimum test cases:

```text
1. Correct policy date → SUPPORTED
2. Incorrect policy date → CONTRADICTED
3. Correct paraphrase → SUPPORTED
4. Unsupported coverage statement → UNSUPPORTED
5. Correct coverage explanation → SUPPORTED
6. Empty answer → deterministic failure
7. Missing TaskResult[] → deterministic failure
8. First validation failure → one regeneration
9. Second validation failure → HANDOFF
10. Critical-flow invariant violation → REJECT
```

For grounding Model B, evaluation matters more than intuition.

We should measure false positives and false negatives before choosing production thresholds.

---

# 27. Implementation order

Recommended T5.9 sequence:

```text
T5.9a
Validation contract and schemas

        ↓

T5.9b
Deterministic base guards

        ↓

T5.9c
GroundingFactBuilder
structured TaskResult[] → granular GroundingFact[] with provenance IDs

        ↓

T5.9d
GroundingValidator
Model B + structured result

        ↓

T5.9e
Decision policy
guards + grounding → action

        ↓

T5.9f
Single automatic regeneration

        ↓

T5.9g
Safe fallback / handoff

        ↓

T5.9h
Complexity-aware validation routing

        ↓

T5.9i
Validator model selection evaluation

        ↓

T5.9j
Regression tests / grounding eval set
```

---

# 28. Final runtime

```text
                           USER QUESTION
                                │
                                ▼
                           ChatService
                                │
                                ▼
                        Runtime execution
                                │
                                ▼
                     STRUCTURED TaskResult[]
                       ┌────────┴─────────┐
                       │                  │
                       ▼                  ▼
               PolicyTaskContent   RetrievalTaskContent
                       │                  │
                       └────────┬─────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
         ContextBuilder                 GroundingFactBuilder
                │                                │
                ▼                                ▼
      LLM-friendly context               GroundingFact[]
                │                                │
                ▼                                │
             Model A                             │
            Generator                            │
                │                                │
                ▼                                │
          Draft Answer ──────────────────────────┘
                                │
                                ▼
                       ResponseValidator
                                │
               ┌────────────────┴────────────────┐
               │                                 │
               ▼                                 ▼
       Deterministic Guards              GroundingValidator
              Python                         Model B
               │                                 │
               │                          claim ↔ evidence
               │                                 │
               └────────────────┬────────────────┘
                                ▼
                     ValidationDecisionPolicy
                                │
                ┌───────────────┼────────────────┐
                │               │                │
                ▼               ▼                ▼
               OK          REGENERATE         HANDOFF
                                │
                                ▼
                         maximum one retry
```

The key property of this runtime is that **Model A and Model B are derived from the same trusted structured `TaskResult[]`**.

`ContextBuilder` changes representation for generation.

`GroundingFactBuilder` changes representation for validation.

Neither component re-queries the database or reconstructs data from generated natural language.

---

# 29. Final design decisions

For this project we choose:

```text
YES:
- typed structured TaskResult[] as the shared trusted transport
- PolicyTaskContent for customer contract data
- RetrievalTaskContent with individual chunk IDs and metadata
- ContextBuilder formats TaskResult[] for Model A
- GroundingFactBuilder converts the same TaskResult[] into Model B evidence
- semantic grounding checker
- structured grounding result
- deterministic backend guards
- backend-owned decision policy
- maximum one regeneration attempt
- safe handoff after repeated failure
- validation telemetry and regression tests
```

```text
NO:
- flattening PolicyService / RetrievalService results into strings inside ChatService
- json.dumps() as the TaskResult transport format
- rebuilding source identity after it has already been discarded
- manual regex parsing as the primary validator
- rebuilding every date/money/status from free-form answer text
- trusting Model A's own self-reported facts as the only evidence
- allowing Model B to decide backend execution directly
- infinite regeneration loops
- letting validator use outside insurance knowledge
```

The architecture can be summarized as:

```text
Generator creates the answer.

Trusted services provide the truth.

Grounding checker verifies semantic support.

Backend guards enforce hard rules.

ResponseValidator decides whether the answer is safe to release.
```
