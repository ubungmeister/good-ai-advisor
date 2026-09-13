<img width="1536" height="1024" alt="ChatGPT Image 30 авг  2026 г , 15_17_54" src="https://github.com/user-attachments/assets/37e5dd9c-b6b9-4778-9c85-8be8970846b9" />


                         
                         USER MESSAGE
                              │
                              ▼
                      ┌───────────────┐
                      │ Safety Gateway │
                      └───────┬───────┘
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
            NORMAL          HIGH RISK      BLOCKED
               │              │
               │              └──→ Emergency / escalation flow
               │
               ▼
          Intent Router
               │
        ┌──────┼────────┐
        ▼      ▼        ▼
     POLICY   CLAIM   GENERAL
        │
        ▼
 PolicyService + RetrievalService
        │
        ▼
    ContextBuilder
        │
        ▼
      LLM
        │
        ▼
 Response Validator
        │
        ▼
      USER
