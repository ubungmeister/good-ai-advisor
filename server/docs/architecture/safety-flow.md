# Safety Flow

Recommended project location:

```text
docs/architecture/safety-flow.md
```

This document describes how a user message moves through the safety layer before the normal insurance RAG flow.

## High-level flow

```text
User
 ↓
SafetyClassifier
 ↓
SafetyDecision
 ↓
SafetyRouter
 ↓
        ┌───────────────┐
        ↓               ↓
 CRITICAL_FLOW      NORMAL_FLOW
        ↓               ↓
CriticalFlow       RetrievalService
Service                 ↓
        ↓               RAG
      answer              ↓
                         LLM
                          ↓
                        answer
```

## What each step does

### 1. User

The original user message enters `ChatService`.

Example:

```text
Měl jsem nehodu a nemůžu dýchat.
```

### 2. SafetyClassifier

`SafetyClassifier` analyzes the raw user message and answers only:

> Is the user's current situation critical?

```python
safety_decision = await self.safety_classifier.classify(
    message=message,
)
```

`message` is the raw input.  
`safety_decision` is the structured interpretation.

### 3. SafetyDecision

Example:

```python
SafetyDecision(
    is_critical=True,
    category=SafetyCategory.MEDICAL_EMERGENCY,
    evidence=["nemůžu dýchat"],
)
```

It contains:

- `is_critical`
- `category`
- `evidence`

Think of it as:

```text
message
   ↓
classification
   ↓
SafetyDecision
```

### 4. SafetyRouter

`SafetyRouter` does not call an LLM. It receives the already-created decision and chooses a route:

```python
safety_route = self.safety_router.route(
    decision=safety_decision,
)
```

Conceptually:

```text
SafetyDecision
      ↓
is_critical?
   ↙         ↘
 yes         no
 ↓            ↓
CRITICAL    NORMAL
```

The classifier answers:

> What is happening?

The router answers:

> Where should this request go?

## Critical flow

If:

```python
safety_route == SafetyRoute.CRITICAL_FLOW
```

then:

```python
return self.critical_flow_service.handle(
    decision=safety_decision,
)
```

Because of `return`, Python stops executing `generate_answer()`.

The request does not continue to the normal RAG pipeline.

```text
CRITICAL_FLOW
      ↓
CriticalFlowService
      ↓
approved / deterministic handling
      ↓
answer
```

Trusted emergency contacts and procedures should come from company-controlled data, not be invented by the LLM.

## Normal flow

If the request is not critical, execution continues:

```text
NORMAL_FLOW
     ↓
RetrievalService
     ↓
RAG
     ↓
LLM
     ↓
answer
```

The original `message` is used again:

```python
retrieval_results = self.retrieval_service.search(
    db=db,
    question=message,
    limit=5,
)
```

and later:

```python
answer = await self.llm_service.generate_answer(
    system_prompt=system_prompt,
    user_message=message,
    context=context,
)
```

## Important mental model

```text
message
= raw user input

safety_decision
= what SafetyClassifier understood

safety_route
= where the backend sends the request
```

Short version:

```text
message  → what did the user say?
decision → what does it mean for safety?
route    → where do we go next?
```

## Responsibilities

```text
SafetyClassifier
= AI classification

SafetyDecision
= structured + validated data

SafetyRouter
= deterministic routing

CriticalFlowService
= critical handling

RetrievalService
= normal insurance knowledge retrieval

LLMService
= final normal-flow answer generation
```

Key enterprise principle:

```text
AI understands the request.
Backend controls execution.
```
