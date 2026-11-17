# Audit progress

Updated 2026-11-17. Original audit target: `e99500e`.

- **3.1–3.3:** addressed by `0555eb5` (chunking, ingestion, retrieval script scope,
  and setup documentation). A full fresh-database setup remains an acceptance check.
- **3.6:** mitigated for a local synthetic demo. Chat and policy callers cannot
  choose the user identity. Chat, policies, users/me, and the LLM test endpoint share
  a server-configured ACTIVE user and refuse access outside explicit development
  mode. Conversation and policy ownership are checked before history access or
  message persistence. Sensitive runtime prints were removed, including those in
  retrieval, policy lookup and validation. Request timing logs use route templates.
  Real production authentication and deployment access-log configuration remain open.
- **3.4:** next: add a reviewed end-to-end AI benchmark for answer correctness,
  grounding, validator acceptance/rejection, clarification and handoff behavior.
- **3.5, 3.7–3.11:** remain open: reranker documentation, test organization/CI,
  broader error classification, concurrent inference, cleanup and UI citations.

Security regression coverage lives in `tests/services/test_identity_access.py`;
regeneration logging coverage lives in `app/services/test/test_chat_service_regeneration.py`.
These tests use mocked database/model collaborators; they are not production
authentication tests or measurements of AI answer quality.
