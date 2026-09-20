<img width="1536" height="1024" alt="ChatGPT Image 30 авг  2026 г , 15_17_54" src="https://github.com/user-attachments/assets/37e5dd9c-b6b9-4778-9c85-8be8970846b9" />

# AI Insurance Assistant — Enterprise Runtime Flow

```text
                              USER MESSAGE
                                   │
                                   ▼
                              ChatService
                                   │
                                   ▼
                              SafetyRouter
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
                  CRITICAL                    NORMAL
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                              QueryPlanner
                                   │
                    Split message into 1..N tasks
                                   │
                                   ▼
                            TaskPrioritizer
                                   │
                    Decide which task comes first
                                   │
                                   ▼
                               TaskRouter
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        PolicyService       RetrievalService      Other Services
              │                    │                 / Tools
              │                    │                    │
              │                    │          ClaimService
              │                    │          PaymentService
              │                    │          ContactService
              │                    │          DocumentService
              │                    │          EmergencyService
              │                    │          External APIs
              │                    │                    │
              └────────────────────┴────────────────────┘
                                   │
                                   ▼
                              Task Results
                                   │
                                   ▼
                             ContextBuilder
                                   │
                    Combine only required data:
                                   │
                    - policy facts
                    - RAG document chunks
                    - task results
                    - conversation history
                    - system instructions
                                   │
                                   ▼
                               LLMService
                                   │
                                   ▼
                          ResponseValidator
                                   │
                      ┌────────────┴────────────┐
                      ▼                         ▼
                     OK                       REJECT
                      │                         │
                      ▼                         ▼
                    USER                  Regenerate /
                                          Safe fallback /
                                          Human handoff



                    Question
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
          E5 Top 20       Lexical Top 20
              ↓                 ↓
              └────────┬────────┘
                       ↓
                  RRF fusion
                       ↓
                12 unique chunks
                       ↓
               MiniLM reranker
                       ↓
                   Top 5
