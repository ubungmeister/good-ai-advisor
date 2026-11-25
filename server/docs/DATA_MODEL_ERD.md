# Good AI Advisor data model ERD

This page maps the current SQLAlchemy data model into three views: the insurance contract and product catalogue, the document retrieval corpus, and chat evidence/audit records. It is based on `server/app/models/`; each entity shows the main identifiers and relationships rather than every implementation column.

## 1. Policy and product catalogue

A policy belongs to a user, selects a plan and product version, and stores policy-level coverage records. `PolicyPerson` links people to policies with a role and optional coverage dates.

```mermaid
erDiagram
    persons o|--|| users : identifies
    users ||--o{ policies : owns
    persons ||--o{ policy_persons : participates_as
    policies ||--o{ policy_persons : covers_people

    products ||--o{ product_versions : versions
    product_versions ||--o{ plans : offers
    product_versions ||--o{ policies : version_recorded_on
    plans ||--o{ policies : selected_by
    plans ||--o{ plan_coverages : defines
    coverage_types ||--o{ plan_coverages : classifies

    policies ||--o{ policy_coverages : records
    coverage_types ||--o{ policy_coverages : classifies
    policy_persons o|--o{ policy_coverages : may_scope
    plan_coverages o|--o{ policy_coverages : source_for

    policies ||--o{ policy_options : has
    policies ||--o| travel_policy_details : has_travel_details
    policies ||--o{ policy_documents : has_documents

    users {
        uuid id PK
        uuid person_id FK "unique"
        string email UK
        string status
    }
    persons {
        uuid id PK
        string first_name
        string last_name
        date date_of_birth
        string phone
    }
    policies {
        uuid id PK
        uuid owner_user_id FK
        uuid product_version_id FK
        uuid plan_id FK
        string policy_number UK
        string policy_status
        date start_date
        date end_date
    }
    policy_persons {
        uuid id PK
        uuid policy_id FK
        uuid person_id FK
        string role
        date coverage_start
        date coverage_end
    }
    products {
        uuid id PK
        string code UK
        string name
    }
    product_versions {
        uuid id PK
        uuid product_id FK
        string version
        date valid_from
        date valid_to
    }
    plans {
        uuid id PK
        uuid product_version_id FK
        string code
        string name
    }
    coverage_types {
        uuid id PK
        string code UK
        string name
    }
    plan_coverages {
        uuid id PK
        uuid plan_id FK
        uuid coverage_type_id FK
        boolean included
        decimal limit_amount
        string currency
    }
    policy_coverages {
        uuid id PK
        uuid policy_id FK
        uuid coverage_type_id FK
        uuid policy_person_id FK "nullable"
        uuid source_plan_coverage_id FK "nullable"
        decimal limit_amount
        decimal deductible_value
    }
    policy_options {
        uuid id PK
        uuid policy_id FK
        string code
        boolean selected
        decimal premium_amount
    }
    travel_policy_details {
        uuid policy_id PK, FK
        string coverage_mode
        string territory
        string trip_purpose
        string sport_level
    }
    policy_documents {
        uuid id PK
        uuid policy_id FK
        string document_type
        string storage_uri
        boolean contains_pii
    }
```

### Coverage interpretation

`PlanCoverage` is the reusable catalogue definition. `PolicyCoverage` is the coverage recorded on a specific purchased policy, with its own limit/deductible fields and an optional `source_plan_coverage_id` for provenance. That link does not mean the policy reads the plan row's values dynamically. If policy records are copied from the plan, application logic should validate the copy and explicitly handle approved overrides.

## 2. Product documents and retrieval chunks

Insurance wording is attached to a product version. Each document is split into chunks; chunks store text and an optional vector embedding used by retrieval.

```mermaid
erDiagram
    products ||--o{ product_versions : versions
    product_versions ||--o{ knowledge_documents : has_terms_documents
    knowledge_documents ||--o{ document_chunks : split_into

    product_versions {
        uuid id PK
        uuid product_id FK
        string version
        date valid_from
        date valid_to
    }
    knowledge_documents {
        uuid id PK
        uuid product_version_id FK
        string title
        string document_type
        string language
        string ingestion_status
        string storage_uri
    }
    document_chunks {
        uuid id PK
        uuid document_id FK
        int chunk_index
        string article_number
        text content
        vector embedding "384 dimensions, nullable"
    }
```

## 3. Conversations, sources, and AI run records

A conversation belongs to a user and may be associated with a policy. Messages belong to conversations. Message sources preserve links to evidence used in answers, while AI runs keep execution metadata.

```mermaid
erDiagram
    users ||--o{ conversations : owns
    policies o|--o{ conversations : context_for
    conversations ||--o{ messages : contains
    messages ||--o{ message_sources : cites
    document_chunks o|--o{ message_sources : document_evidence
    policy_coverages o|--o{ message_sources : policy_evidence
    policy_options o|--o{ message_sources : option_evidence
    conversations o|--o{ ai_runs : has_runs
    messages o|--o{ ai_runs : generated_or_checked_by

    conversations {
        uuid id PK
        uuid user_id FK
        uuid policy_id FK "nullable"
        string title
        datetime created_at
    }
    messages {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        datetime created_at
    }
    message_sources {
        uuid id PK
        uuid message_id FK
        string source_type
        uuid document_chunk_id FK "nullable"
        uuid policy_coverage_id FK "nullable"
        uuid policy_option_id FK "nullable"
        decimal relevance_score
    }
    ai_runs {
        uuid id PK
        uuid conversation_id FK "nullable"
        uuid message_id FK "nullable"
        string model_provider
        string model_name
        int latency_ms
        int retrieval_count
        string safety_result
    }
```

## Notes for reading

- `users.person_id` is unique and required, so each user maps to one person; a person can exist without a user account.
- The model has separate `policies.plan_id` and `policies.product_version_id` foreign keys. The ERD shows both as stored; it does not imply the database alone guarantees the chosen plan belongs to that product version.
- A nullable `message_sources` evidence foreign key means source rows may represent one of several evidence kinds. The model layer should validate that each source row is internally consistent.
- `PolicyDocument` represents a document attached to a customer's policy. `KnowledgeDocument` represents product wording used for retrieval; these are separate document purposes.
