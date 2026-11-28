# Good AI Advisor

This context describes how a policyholder's purchased travel insurance is understood using the policy-specific facts and the insurer's product terms.

## Language

**Policy**:
A specific travel insurance contract held by a **Policyholder**. It records the insured people, coverage period, selected benefits, limits, and other contract-specific details.

**Policyholder**:
The person who enters into the insurance contract with the insurer. The policyholder may differ from an **Insured Person**.

**Insured Person**:
A person protected by one or more coverages under a **Policy**.

**Policy Coverage**:
A benefit recorded as included in a particular **Policy**, with its own limit or deductible where specified. Its presence does not by itself establish that a specific event satisfies the **Insurance Terms**.

**Insurance Terms**:
The insurer's official, product-version-specific wording that defines benefits, conditions, exclusions, and duties. The terms describe the product; a **Policy** identifies what applies to a particular customer.

**Conversation**:
A chat thread associated with exactly one **Policy** for its lifetime. A user may have multiple conversations, including multiple conversations about the same policy.

**Message**:
A single question from the user or answer from the adviser within a **Conversation**.

**Support Procedure**:
An approved, product-scoped practical instruction for helping a customer handle an insurance scenario; it is guidance, not an **Insurance Terms** provision or a coverage determination.
_Avoid_: Policy rule, contractual clause, guaranteed claim outcome

**Support Publication**:
The domain state in which a **Support Procedure** has passed expert review, has authoritative provenance, has a valid effective period and product scope, and is eligible for customer-facing retrieval.
_Avoid_: Ingested, indexed, ready

**Applicability Scope**:
The explicit boundary describing which product versions a **Support Procedure** may guide: an exact product version, an approved version-independent rule, or no customer-facing applicability until reviewed.
_Avoid_: Empty means all, unbounded applicability

**Knowledge Collection**:
A logically distinct evidence source used by the adviser, such as contractual **Insurance Terms** or approved **Support Procedures**, with its own eligibility and retrieval rules.
_Avoid_: Undifferentiated corpus, mixed evidence

**Evidence Route**:
The planner's declaration of which evidence obligations an answer has: **POLICY**, **SUPPORT**, **BOTH**, or **NONE**.
_Avoid_: Search mode, keyword route

**Evidence Lane**:
The source-specific set of evidence supplied to generation and validation for one **Knowledge Collection**; a combined answer may contain separate policy and support lanes without treating them as interchangeable.
_Avoid_: Flat evidence list, blended authority

**Support Evidence Unit**:
The complete approved support procedure retrieved for a scenario, including its conditions, steps, required or recommended documents, and escalation guidance; question variations help find it but are not standalone evidence.
_Avoid_: Isolated support step, snippet-only procedure

**Canonical Knowledge Language**:
The language in which approved knowledge is stored and retrieved; customer response language is a separate presentation concern.
_Avoid_: User language, answer language

**Lane Validation**:
Validation that each factual claim is supported by the correct **Evidence Lane**: policy claims by policy evidence and practical procedure claims by support evidence.
_Avoid_: Generic groundedness, similarity-only validation

**Support Retrieval Miss**:
The state in which no approved and applicable **Support Evidence Unit** survives retrieval and eligibility checks; it is not permission to use draft guidance or invent a procedure.
_Avoid_: Best effort, probably applicable

**Retrieval Policy**:
The source-specific rules for candidate generation, ranking, filtering, and evidence limits used by a **Knowledge Collection**.
_Avoid_: One-size-fits-all search settings

**Retrieval Service Boundary**:
The independent service boundary around a collection's retrieval behavior; generic infrastructure may be reused, but ranking and acceptance behavior is owned by the collection.
_Avoid_: Shared search behavior

**Ambiguous Insurance Question**:
An insurance-related request whose required evidence cannot be confidently limited to one collection; it is conservatively treated as requiring both policy and support consideration.
_Avoid_: Low-confidence guess, policy-only by default

**Evidence Conflict**:
A material inconsistency between applicable policy evidence and support guidance, or between two applicable sources within a lane, that cannot be safely resolved by the declared authority rules.
_Avoid_: Ranking disagreement, harmless wording difference

**Evaluation Mode**:
A non-customer execution path allowed to inspect or test non-publishable knowledge, with its status visible and its evidence excluded from normal answer generation.
_Avoid_: Temporary production bypass, TODO-only safety

**Clarification Loop**:
An iterative interaction in which retrieved evidence identifies missing facts, the adviser asks a targeted question, and the answer is replanned and retrieved again until the procedure is applicable or a bounded fallback is reached.
_Avoid_: Fixed questionnaire, unlimited questioning
