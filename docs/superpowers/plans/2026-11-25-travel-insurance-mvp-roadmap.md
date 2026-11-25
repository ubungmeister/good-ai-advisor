# Travel Insurance MVP Vertical-Slice Plan

> **For agentic workers:** Do not implement until the user asks to start. When implementation is authorized, use `superpowers:executing-plans` to work through this plan task by task.

**Goal:** Deliver a hosted synthetic-data MVP where authenticated users can view their pre-linked travel policies, create policy-bound conversations, ask insurance questions, and reload saved message history.

**Architecture:** React is hosted on Vercel; FastAPI remains the application backend on Render; Supabase provides Auth and Postgres/pgvector. Supabase Auth's UUID is the canonical app user ID. FastAPI verifies tokens and enforces ownership for every policy and conversation request. The existing Python chat-answer pipeline is reused; policy purchase, issuance, and user policy upload are out of scope.

**Tech Stack:** React, TypeScript, Vite; FastAPI, SQLAlchemy, Alembic, psycopg; Supabase Auth, Postgres, pgvector; Render; Vercel.

**Spec:** `README.md` plus the scope and technical decisions approved in the OpenCode conversation on 2026-11-25. This plan is a roadmap; it is not authorization to implement.

## Global Constraints

- Use synthetic policy and customer data until the database-protection review is complete.
- Use the Supabase Auth UUID as `users.id`; migrate or reseed dependent local data before hosted use.
- A conversation must belong to exactly one authenticated user and exactly one policy.
- FastAPI must check ownership on every policy and conversation operation; never trust a client-supplied user ID.
- Do not expose a database URL, password, or Supabase service-role key to the browser.
- Preserve the existing Python `ChatService`, retrieval, and validation pipeline where it fits.
- Policy purchase, policy issuance, and policy-document ingestion are out of scope.
- Evidence citations remain deferred; track them in GitHub issue #3.
- No implementation is authorized by this roadmap alone.

## Review Focus

- A missing, expired, malformed, or wrong-issuer JWT must not resolve to a user.
- A user must not list or read another user's policy, conversation, or messages.
- A conversation with a null, foreign, or changed policy must be rejected.
- An old local user UUID must not leave orphaned policy or conversation ownership after migration.
- Database connectivity, connection resets, or model initialization failures must fail health checks rather than appear as valid chat responses.
- RAG evaluation must distinguish missing policy facts, missing source knowledge, retrieval misses, and answer/validation failures.

---

### Task 1: Resolve and record deployment and data-access decisions

**Dependencies:** None.

**Files:** No application files. Record decisions only after review; do not create or alter `docs/product-scope.md` without approval.

- [ ] Confirm the Auth-to-app identity rule: `users.id` equals the Supabase Auth UUID. For the seeded account, create the Auth user first and use its UUID for the app `User` row and the linked `Person` row.
- [ ] Select the FastAPI database role and decide whether RLS is required for the synthetic-data MVP. Direct SQLAlchemy connections do not automatically carry the browser JWT into RLS. Before real customer data, complete a separate database-protection review.
- [ ] Select a Render-to-Supabase connection mode after testing the actual Render environment. Supabase recommends direct connections for persistent backends when reachable; its session pooler is the IPv4 alternative. Do not select transaction pooling by default for this persistent FastAPI service.
- [ ] Agree on the initial hosted environment (staging/demo) and confirm that it contains synthetic data only.

**Completion check:** The identity mapping, database ownership boundary, connection-mode decision, and synthetic-only environment are explicitly approved before implementation begins.

### Task 2: Prepare Supabase schema and migrate the synthetic dataset

**Dependencies:** Task 1.

**Files:** `server/migrations/`, `server/scripts/seed_dev.py`, and a reviewed one-time migration/export script if local rows are preserved.

- [ ] Apply the existing Alembic migrations to the Supabase project, including required vector and lexical-search extensions.
- [ ] Create the Supabase Auth test user and record its Auth UUID.
- [ ] Produce an old-user-UUID to Auth-UUID mapping for any local rows being preserved. Update `users.id` and dependent owner references, including `policies.owner_user_id` and `conversations.user_id`, in a transaction. If the hosted dataset is only the current synthetic fixture, prefer reseeding it with the Auth UUID rather than preserving disposable records.
- [ ] Create the corresponding `User` and `Person` rows; load the synthetic policy and knowledge data.
- [ ] Ensure newly created conversations require a policy. Existing nullable `conversations.policy_id` values must be mapped or removed before enforcing the required relationship.

**Verification:** From `server`, run `alembic upgrade head` and `alembic current`; verify migration/data row counts, foreign-key integrity, and ownership mappings. Run `python -m scripts.check_demo_setup` and confirm the synthetic policy retrieves embedded VPP chunks for its product version.

### Task 3: Verify Render connectivity and RAG model startup early

**Dependencies:** Tasks 1–2.

**Files:** `server/app/core/config.py`, `server/app/db/database.py`, `server/app/main.py`, and Render environment configuration, only as needed after the technical decision.

- [ ] Deploy a minimal FastAPI service to the intended Render service size, with Supabase credentials stored only in Render environment settings.
- [ ] Test database connection, migrations, vector search, and reconnect behavior from Render.
- [ ] Measure E5, CrossEncoder, and Stanza initialization time and memory. The current lifespan initializes retrieval services before serving requests.
- [ ] If startup or memory is unacceptable, stop and review options (service size, model loading strategy, or separating model work) before proceeding.

**Verification:** Render health check succeeds after model initialization; a known retrieval query returns expected scoped chunks; startup time and peak memory are recorded and accepted. No credentials appear in logs or frontend build output.

### Task 4: Add Supabase JWT identity and verify policy access

**Dependencies:** Tasks 1–3.

**Files:** `server/app/core/identity.py`, `server/app/core/config.py`, existing `server/app/api/users.py` and `server/app/api/policies.py`, plus focused tests under `server/tests/`.

- [ ] Replace the deployed development-only identity path with Supabase JWT verification using the project's signing keys/JWKS; derive the app user ID from the verified token subject.
- [ ] Keep local automated tests isolated with dependency overrides; never fall back to the configured demo identity in a deployed environment.
- [ ] Preserve the existing `/api/users/me` and `/api/policies` behavior, now authenticated by the verified user.
- [ ] Configure the React client to obtain a Supabase session and send its access token as a bearer token to FastAPI.

**Verification:** Tests prove missing, expired, malformed, and invalid-signature tokens are rejected; a valid token resolves the expected `User`; `/api/policies` returns only that user's policies; another user's policy is not disclosed.

### Task 5: Expose policy-bound conversation and message history APIs

**Dependencies:** Task 4.

**Files:** Add `server/app/api/conversations.py`; update `server/app/main.py`, `server/app/models/conversation.py`, `server/app/schemas/chat.py`, `server/app/services/conversation_service.py` as needed; add Alembic migration and API/service tests.

- [ ] Expose authenticated operations to create a conversation for an owned policy, list the user's conversations, and load messages for an owned conversation.
- [ ] Reuse `ConversationService.get_user_conversations`, `get_messages`, and existing ownership checks rather than duplicating repository logic.
- [ ] Enforce one policy per conversation. A continuation must keep the original policy; selecting a different policy requires a new conversation.
- [ ] Preserve chronological message order and the existing chat persistence path.

**Verification:** API tests cover create/list/load, policy immutability, null/foreign policy rejection, and cross-user conversation/message access denial. Run `python -m pytest tests app/services/test` from `server`.

### Task 6: Complete the first end-to-end React slice

**Dependencies:** Tasks 4–5.

**Files:** `ui/src/App.tsx`, `ui/src/api/chat.ts`, new focused API/auth components as needed, and `ui/.env.example`.

- [ ] Add sign-in/sign-out with Supabase Auth and keep access tokens out of persistent browser storage beyond the SDK's supported session handling.
- [ ] Load the signed-in user's policy list; if there are multiple policies, require selection for a new conversation.
- [ ] Create or reopen a conversation, send one known question through the existing `POST /chat` and `ChatService`, and display the selected policy and messages.
- [ ] Reload the page, reopen the conversation, and restore its saved messages from FastAPI.
- [ ] Keep the slice intentionally small: no policy purchase/issuance, policy upload, citations, or RAG tuning.

**Verification:** In a deployed test environment, sign in as User A, select a policy, send the known question, refresh, and confirm the same policy and ordered user/assistant messages return. Repeat as User B and confirm User A's policy/conversation cannot be accessed. Run `npm run lint` and `npm run build` in `ui`.

### Task 7: Complete the remaining conversation UI

**Dependencies:** Task 6.

**Files:** `ui/src/App.tsx`, focused UI components/styles, and API client modules.

- [ ] Implement the agreed conversation sidebar/history list, New Chat action, policy summary, selected conversation, sign-out, backend status, loading, empty, and error states.
- [ ] Support multiple conversations on one policy and multiple policies on one account; keep the policy fixed within an existing conversation.
- [ ] Keep citation display deferred and tracked in issue #3.

**Verification:** Manual browser walkthrough covers zero/one/many policies, zero/many conversations, reload, failed API request, sign-out, and narrow viewport. Frontend lint/build pass.

### Task 8: Establish RAG and answer-quality confidence

**Dependencies:** Task 6; may proceed alongside Task 7 after the end-to-end slice is stable.

**Files:** `server/data/evals/`, `server/scripts/run_retrieval_eval.py`, `server/scripts/run_ai_eval.py`, and targeted backend tests.

- [ ] Establish a baseline for policy details, general insurance-terms questions, procedures, and policy-plus-terms coverage checks.
- [ ] Expand source-reviewed cases for English/Czech questions, follow-ups, missing evidence, ambiguity, and product-version scoping.
- [ ] Classify each failure as policy-data gap, missing knowledge source, retrieval miss, planning/routing issue, or generation/validation issue before making changes.
- [ ] Improve only the failing component while reusing the existing ChatService, retrieval, and validation pipeline.

**Verification:** Run `python -m pytest tests app/services/test`, `python -m scripts.run_retrieval_eval`, and `python -m scripts.run_ai_eval --check` from `server`; review source labels and representative answers. No quality claim is based only on retrieval Hit@K.

### Task 9: Measure and improve answer speed

**Dependencies:** Task 8 baseline; Task 3 Render measurements.

**Files:** Existing timing instrumentation, `server/scripts/test_retrieval_latency.py`, and focused performance tests or reports.

- [ ] Measure cold-start, warm retrieval, reranking, LLM generation, validation, and end-to-end hosted chat latency.
- [ ] Agree on response-time targets before optimizing.
- [ ] Optimize only measured bottlenecks and retain the quality baseline.

**Verification:** Run `python -m scripts.test_retrieval_latency`; record hosted latency percentiles and startup/memory results; rerun answer-quality tests after optimization.

### Task 10: Complete production-protection review and hosted release

**Dependencies:** Tasks 6–9.

**Files:** Deployment configuration for Vercel/Render/Supabase, `server/app/main.py` CORS configuration, health checks, and operational documentation.

- [ ] Make allowed frontend origins environment-specific; configure secrets and database credentials only in provider secret settings.
- [ ] Complete the database-protection review (ownership enforcement, DB role, and RLS decision) before any real user data is admitted.
- [ ] Review migrations, backups, logs, rate/cost limits, provider failure handling, and health checks for the hosted synthetic-data MVP.
- [ ] Deploy the reviewed Vercel frontend, Render API, and Supabase project.

**Verification:** Deployed smoke test covers sign-in, user isolation, policy selection, conversation persistence, and one answer. Backend and frontend verification commands pass; no real user data is used until the protection review is signed off.
