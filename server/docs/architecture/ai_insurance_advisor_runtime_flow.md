# AI Insurance Advisor — Runtime Flow

## Overview

The runtime is designed around one core principle:

> **AI understands intent. Backend controls execution. Services provide trusted data. RAG provides relevant knowledge. LLM explains. Validator protects the output.**

The LLM is used to understand the user's intent and generate the final natural-language answer, but it does **not** directly decide which backend services to call.

---

## High-Level Flow

```text
┌──────────────────────────────────────────────┐
│ USER                                         │
│ "Does my insurance cover skiing?"            │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ ChatService                                  │
│ Main orchestrator                            │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ SafetyClassifier                 ← LLM #1     │
│                                              │
│ Question:                                    │
│ "Is this a critical/emergency situation?"    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
                 SafetyDecision
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ SafetyRouter                     ← NO LLM     │
│                                              │
│ is_critical?                                 │
└───────────────┬───────────────────────┬──────┘
                │ YES                   │ NO
                ▼                       ▼
       CRITICAL_FLOW                NORMAL_FLOW
                │                       │
                ▼                       ▼
       CriticalFlowService      ┌───────────────────────────┐
       deterministic            │ QueryPlanner    ← LLM #2  │
                │               │                           │
                ▼               │ "What does the user want?"│
             ANSWER             └──────────────┬────────────┘
                                              │
                                              ▼
                                          QueryPlan
                                              │
                                              ▼
                                   ┌───────────────────────┐
                                   │ PlannedTask           │
                                   │                       │
                                   │ type                  │
                                   │ query                 │
                                   │ evidence              │
                                   └───────────┬───────────┘
                                               │
                                               ▼
                                   ┌───────────────────────┐
                                   │ TaskPrioritizer       │
                                   │        NO LLM         │
                                   │                       │
                                   │ Orders tasks          │
                                   │ deterministically     │
                                   └───────────┬───────────┘
                                               │
                                               ▼
                                   ┌───────────────────────┐
                                   │ TaskRouter            │
                                   │        NO LLM         │
                                   │                       │
                                   │ TaskType              │
                                   │     ↓                 │
                                   │ targets[]             │
                                   └───────────┬───────────┘
                                               │
                          ┌────────────────────┴───────────────────┐
                          │                                        │
                          ▼                                        ▼
                ┌──────────────────┐                    ┌──────────────────┐
                │ PolicyService    │                    │ RetrievalService │
                │                  │                    │                  │
                │ User's actual    │                    │ Official policy  │
                │ contract facts   │                    │ documents / RAG  │
                └─────────┬────────┘                    └─────────┬────────┘
                          │                                        │
                          └────────────────────┬───────────────────┘
                                               │
                                               ▼
                                       TaskResult[]
                                               │
                                               ▼
                                   ┌───────────────────────┐
                                   │ ContextBuilder        │
                                   │        NO LLM         │
                                   │                       │
                                   │ Combines trusted      │
                                   │ results into one      │
                                   │ structured context    │
                                   └───────────┬───────────┘
                                               │
                                               ▼
                                ┌──────────────────────────┐
                                │ LLMService      ← LLM #3 │
                                │                          │
                                │ Generates one coherent   │
                                │ answer from trusted      │
                                │ context                  │
                                └────────────┬─────────────┘
                                             │
                                             ▼
                                  ResponseValidator
                                      ← T5.9 / next step
                                             │
                                             ▼
                                           USER
```

---

## 1. ChatService

`ChatService` is the main orchestrator.

It does not contain the domain knowledge itself. Its job is to coordinate the runtime:

```text
Safety
→ Planning
→ Prioritization
→ Routing
→ Service execution
→ Context building
→ Final LLM answer
```

Conceptually:

```python
answer = await chat_service.generate_answer(...)
```

---

## 2. SafetyClassifier

The first LLM call analyzes the original user message only for safety.

Example:

```text
"I had an accident and I cannot breathe."
```

The classifier produces a structured result such as:

```text
SafetyDecision
- is_critical = true
- category = MEDICAL_EMERGENCY
- evidence = ["I cannot breathe"]
```

It answers only:

> **Is the user's current situation critical?**

It does not answer insurance questions.

---

## 3. SafetyRouter

`SafetyRouter` is deterministic Python logic.

It receives `SafetyDecision` and chooses:

```text
CRITICAL_FLOW
or
NORMAL_FLOW
```

It does not call an LLM.

```text
SafetyDecision
      ↓
is_critical?
   ↙       ↘
 yes       no
 ↓          ↓
CRITICAL   NORMAL
```

Critical requests go to `CriticalFlowService` and do not continue through the normal insurance flow.

---

## 4. QueryPlanner

For a normal request, `QueryPlanner` uses an LLM to understand the user's intent.

Example:

```text
"Does my insurance cover skiing?"
```

The planner can produce:

```python
PlannedTask(
    type=TaskType.COVERAGE_CHECK,
    query="Does the policy cover skiing?",
    evidence="Does my insurance cover skiing?"
)
```

The important output is the `TaskType`.

Current task types:

```text
GENERAL_QUESTION
COVERAGE_CHECK
PROCEDURE
POLICY_DETAILS
```

The planner understands intent, but it does **not** directly call backend services.

---

## 5. TaskPrioritizer

`TaskPrioritizer` is deterministic.

If the planner creates multiple tasks, the prioritizer decides their execution order.

Example priority:

```text
PROCEDURE
↓
COVERAGE_CHECK
↓
POLICY_DETAILS
↓
GENERAL_QUESTION
```

No LLM is used here.

---

## 6. TaskRouter

`TaskRouter` receives a `TaskType` and maps it to one or more backend targets.

The mapping is deterministic:

```text
GENERAL_QUESTION
        ↓
RETRIEVAL


PROCEDURE
        ↓
RETRIEVAL


POLICY_DETAILS
        ↓
POLICY


COVERAGE_CHECK
        ↓
POLICY + RETRIEVAL
```

Conceptually:

```python
match task.type:

    case TaskType.GENERAL_QUESTION:
        targets = [TaskTarget.RETRIEVAL]

    case TaskType.PROCEDURE:
        targets = [TaskTarget.RETRIEVAL]

    case TaskType.POLICY_DETAILS:
        targets = [TaskTarget.POLICY]

    case TaskType.COVERAGE_CHECK:
        targets = [
            TaskTarget.POLICY,
            TaskTarget.RETRIEVAL,
        ]
```

### Important distinction

The LLM does this:

```text
"This is a COVERAGE_CHECK."
```

The backend then does this:

```text
COVERAGE_CHECK
→ POLICY + RETRIEVAL
```

Therefore, the LLM does not directly control service execution.

---

## 7. PolicyService

`PolicyService` provides trusted facts about the user's actual purchased insurance contract.

Examples:

```text
Policy status
Payment status
Start date
End date
Purchased coverages
Coverage limits
Selected options
Insured people
Person roles
Travel details
Sport level
Territory
```

Example question:

```text
"When does my insurance expire?"
```

The planner produces:

```text
POLICY_DETAILS
```

The router produces:

```text
POLICY
```

Only `PolicyService` is needed because the answer exists directly in the user's contract data.

---

## 8. RetrievalService

`RetrievalService` searches official insurance documentation.

Examples:

```text
VPP / policy conditions
Coverage rules
Exclusions
Claim procedures
Required documents
Definitions
```

Current retrieval pipeline:

```text
Question
   ↓
E5 semantic search
+
Original lexical search
+
Stanza / lemma / synonym lexical search
   ↓
RRF fusion
   ↓
Protected candidates
   ↓
MiniLM reranker
   ↓
Final Top 5 chunks
```

Example question:

```text
"What documents do I need if my baggage is stolen?"
```

Planner:

```text
PROCEDURE
```

Router:

```text
RETRIEVAL
```

No personal policy data is required for the core version of this question.

---

## 9. Why Some Questions Need POLICY + RETRIEVAL

Example:

```text
"Does my insurance cover skiing?"
```

This requires two different kinds of truth.

### POLICY

Answers:

> **What did this customer actually buy?**

For example:

```text
WINTER_SPORTS = selected
sport_level = RECREATIONAL
policy_status = ACTIVE
```

### RETRIEVAL

Answers:

> **What do the official insurance conditions say?**

For example:

```text
What counts as winter sport?
What activities are excluded?
What conditions must be satisfied?
```

The final answer requires both:

```text
Customer contract facts
        +
Official insurance rules
        ↓
Final grounded answer
```

---

## 10. TaskResult

Different services return different kinds of data.

To make the runtime consistent, `ChatService` converts service outputs into a common internal structure:

```python
TaskResult(
    task_type=...,
    target=...,
    content=...,
)
```

Example:

```text
TaskResult #1
target = POLICY
content = user's contract facts

TaskResult #2
target = RETRIEVAL
content = relevant VPP excerpts
```

This gives `ContextBuilder` one predictable input format.

---

## 11. ContextBuilder

`ContextBuilder` does **not** reason about insurance.

It does not:

```text
- decide whether something is covered
- search the database
- perform RAG
- call an LLM
- create insurance facts
```

Its only job is:

> **Take trusted TaskResults and organize them into one clear context for the final LLM.**

Input:

```text
TaskResult[]
```

Example:

```text
POLICY result
+
RETRIEVAL result
```

Output:

```text
[POLICY FACTS]

[TASK: COVERAGE_CHECK]
...

[INSURANCE DOCUMENTATION]

[TASK: COVERAGE_CHECK]
[DOCUMENT 1]
...

[DOCUMENT 2]
...
```

So the mental model is:

```text
Backend service results
        ↓
ContextBuilder
        ↓
LLM-friendly context string
```

A frontend analogy:

```text
API data
  ↓
view model / formatting layer
  ↓
UI
```

Here it is:

```text
Service data
  ↓
ContextBuilder
  ↓
LLM
```

---

## 12. Final LLMService

The final LLM receives:

```text
System rules
+
Original user question
+
ContextBuilder output
```

Its responsibility is to transform trusted facts into one coherent natural-language answer.

Example:

```text
[POLICY FACTS]
Winter sports option is selected.

[INSURANCE DOCUMENTATION]
Skiing is covered under the winter sports extension
under the documented conditions.
```

The LLM can answer:

```text
"Yes, your policy includes the winter sports option,
so skiing is covered under the conditions described
in the insurance terms."
```

The LLM should not invent facts that are not present in the context.

---

## 13. Example Flows

### Example A — Policy-only question

User:

```text
"When does my insurance expire?"
```

Flow:

```text
User
↓
SafetyClassifier
↓
NORMAL_FLOW
↓
QueryPlanner
↓
POLICY_DETAILS
↓
TaskRouter
↓
POLICY
↓
PolicyService
↓
TaskResult(POLICY)
↓
ContextBuilder
↓
LLM
↓
Answer
```

### Example B — Retrieval-only question

User:

```text
"What documents do I need if my baggage is stolen?"
```

Flow:

```text
User
↓
SafetyClassifier
↓
NORMAL_FLOW
↓
QueryPlanner
↓
PROCEDURE
↓
TaskRouter
↓
RETRIEVAL
↓
RetrievalService
↓
TaskResult(RETRIEVAL)
↓
ContextBuilder
↓
LLM
↓
Answer
```

### Example C — Policy + Retrieval question

User:

```text
"Does my insurance cover skiing?"
```

Flow:

```text
User
↓
SafetyClassifier
↓
NORMAL_FLOW
↓
QueryPlanner
↓
COVERAGE_CHECK
↓
TaskRouter
↓
POLICY + RETRIEVAL
↓
┌─────────────────┬──────────────────┐
│ PolicyService   │ RetrievalService │
└────────┬────────┴─────────┬────────┘
         ↓                  ↓
   TaskResult          TaskResult
         └──────────┬───────┘
                    ↓
              ContextBuilder
                    ↓
                   LLM
                    ↓
                 Answer
```

---

## Component Responsibilities

| Component | Main Question | Uses LLM? |
|---|---|---:|
| `ChatService` | How do we coordinate the request? | No |
| `SafetyClassifier` | Is the current situation critical? | Yes |
| `SafetyRouter` | Critical or normal flow? | No |
| `QueryPlanner` | What does the user want? | Yes |
| `TaskPrioritizer` | In what order should tasks run? | No |
| `TaskRouter` | Which backend source(s) are required? | No |
| `PolicyService` | What is in this customer's contract? | No |
| `RetrievalService` | What do official documents say? | No |
| `ContextBuilder` | How do we organize trusted results for the LLM? | No |
| `LLMService` | How do we explain the result naturally? | Yes |
| `ResponseValidator` | Is the generated answer safe and grounded? | Depends on final implementation |

---

## Mental Model

```text
SafetyClassifier
= Is this dangerous?

QueryPlanner
= What does the user want?

TaskPrioritizer
= In what order should we execute tasks?

TaskRouter
= Which backend services are needed?

PolicyService
= What exactly is in the user's contract?

RetrievalService
= What do the official documents say?

ContextBuilder
= Combine trusted results into one context

Final LLM
= Explain the result to the user
```

---

## Core Principle

```text
AI understands intent
        ↓
Backend controls execution
        ↓
Services provide trusted facts
        ↓
RAG provides relevant knowledge
        ↓
ContextBuilder organizes the evidence
        ↓
LLM explains
        ↓
ResponseValidator protects the output
```
