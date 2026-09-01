# Schema Implementation Tasks

This file is the working checklist for expanding the insurance schema.

## Working rule

Complete one task group at a time. Do not start the next schema phase until the current phase has been migrated, seeded, and tested.

Current focus:

```text
CustomerProfile -> Person
```

Do not continue the old policy API work yet.

---

# TASK R1: Replace CustomerProfile with Person

## Goal

Change the identity model from:

```text
User 1:1 CustomerProfile
```

to:

```text
User 1:1 Person
```

A `Person` may exist without a `User` account. This will later allow a policy to cover a spouse or child who cannot log in.

## Target tables

### persons

```text
id              UUID primary key
first_name      varchar(100), required
last_name       varchar(100), required
date_of_birth   date, optional
birth_number    varchar(20), optional
phone           varchar(30), optional
created_at      datetime, required
updated_at      datetime, required
```

### users

```text
id              UUID primary key
person_id       UUID, required, unique, foreign key -> persons.id
email           varchar(255), required, unique
status          varchar(50), required
created_at      datetime, required
updated_at      datetime, required
```

## R1.1: Create the Person ORM model

Create:

```text
server/app/models/person.py
```

Requirements:

- Add all columns from the target `persons` table.
- Use a UUID primary key with `uuid.uuid4` as the Python default.
- Add a one-to-one `user` relationship.
- Use `back_populates` on both sides of the relationship.
- Do not expose `birth_number` through the public API.

Done when:

- `Person` is registered in `app/models/__init__.py`.
- Alembic can see the model metadata.
- Importing the model does not create a circular-import error.

## R1.2: Update the User ORM model

Update:

```text
server/app/models/user.py
```

Required changes:

- Add `person_id` as a foreign key to `persons.id`.
- Make `person_id` unique to enforce one user per person.
- Replace `profile` with a one-to-one `person` relationship.
- Add `updated_at` because it is part of the new target schema.

Do not delete the old `CustomerProfile` model before the data migration is prepared.

Done when:

```python
user.person
person.user
```

both represent the new relationship.

## R1.3: Prepare the Alembic migration

Create one new revision after:

```text
cafbc6e67f93_add_products_and_policies
```

The upgrade must run in this order:

1. Create `persons`.
2. Add nullable `users.person_id`.
3. Copy every row from `customer_profiles` into `persons`.
4. Connect each user to the new person using the old `customer_profiles.user_id`.
5. Verify that no existing user has a null `person_id`.
6. Change `users.person_id` to non-nullable.
7. Add the unique constraint on `users.person_id`.
8. Add `users.updated_at` and populate existing rows.
9. Drop `customer_profiles` only after the copied data is connected.

Important:

- Review the generated migration manually.
- The data-copy statements must be written explicitly; Alembic autogenerate will not create them correctly.
- Test both `upgrade()` and `downgrade()` on a disposable database.
- Do not use the production database as the first migration test.

Migration validation queries should confirm:

```text
number of old customer_profiles == number of migrated persons
every users.person_id is populated
every users.person_id points to an existing person
test@example.com still exists
```

## R1.4: Fix Alembic model registration

Update:

```text
server/migrations/env.py
```

Current risk: it imports only `User` and `CustomerProfile`. Alembic autogenerate must load all application models, otherwise it may miss tables or generate incorrect changes.

Preferred result:

- Import the model package once.
- Ensure `Base.metadata` contains `Person`, `Product`, `ProductVersion`, `Policy`, and all future models.
- Remove duplicate imports currently present in `env.py`.

## R1.5: Update the API schemas

Update:

```text
server/app/schemas/user.py
```

Replace `CustomerProfileResponse` with:

```python
class PersonResponse(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None
    phone: str | None
```

Update `UserResponse` to return:

```text
id
email
status
person
```

Expected response shape:

```json
{
  "id": "uuid",
  "email": "test@example.com",
  "status": "ACTIVE",
  "person": {
    "first_name": "Max",
    "last_name": "Test",
    "date_of_birth": "1995-01-01",
    "phone": "+420000000000"
  }
}
```

Never include `birth_number` in this response.

## R1.6: Update repository loading

Update:

```text
server/app/repositories/user_repository.py
```

Required changes:

- Replace `joinedload(User.profile)` with `joinedload(User.person)`.
- Keep filtering behavior unchanged.
- Keep returning `User | None`.

The service can remain simple for now because authentication is still using `TEST_USER_EMAIL`.

## R1.7: Update the development seed

Update:

```text
server/scripts/seed_dev.py
```

Required behavior:

- Create a `Person` first.
- Attach that person to the test `User`.
- Keep the seed idempotent: running it twice must not duplicate the user or person.
- Keep the current test email so `/api/users/me` continues to find the same account.

Do not rely only on email when deciding whether a standalone person already exists. For this development seed, loading the existing user and checking `user.person` is sufficient.

## R1.8: Register and verify the users API

Review:

```text
server/app/main.py
server/app/api/users.py
```

The users router exists, but `main.py` currently registers only the chat router. Add the users router before testing `/api/users/me`.

Expected endpoint:

```http
GET /api/users/me
```

Expected result:

```text
HTTP 200
response contains person
response does not contain profile
response does not contain birth_number
```

## R1.9: Tests and acceptance checklist

Minimum tests:

- Migration upgrades a database containing the existing seeded user.
- Existing profile data appears in `persons` after migration.
- `users.person_id` is non-null and unique.
- A `Person` can exist without a `User`.
- A second `User` cannot reference the same `Person`.
- User repository loads the related person.
- `GET /api/users/me` returns HTTP 200.
- API response uses `person`, not `profile`.
- API response never exposes `birth_number`.
- Seed can run twice without duplicating data.

R1 is complete only when all checks pass.

---

# NEXT TASK: R2 Add Plan

Start only after R1 is complete.

Brief scope:

- Create the `plans` table and ORM model.
- Link each plan to one `ProductVersion`.
- Add `ProductVersion.plans` and `Plan.product_version` relationships.
- Add a unique constraint for `(product_version_id, code)`.
- Seed `Standard`, `Dominant`, and `Premiant` plans.
- Test ORM navigation in both directions.

This task will receive its own detailed checklist after R1 is finished.

---

# FUTURE BACKLOG

Keep these items brief until the preceding task is complete:

1. **R3: Refactor Policy** — replace `product_version_id` with `plan_id`, rename `user_id` to `owner_user_id`, and move travel-only fields out of `policies`.
2. **Travel policy details** — add the one-to-one `travel_policy_details` table.
3. **Coverage catalogue** — add `coverage_types` and `plan_coverages`.
4. **Policy persons** — connect policies to policyholders and insured persons.
5. **Purchased coverages** — add contract-specific `policy_coverages`.
6. **Policy options** — add selected add-ons and variants.
7. **Policy documents** — store private policy-document metadata separately from shared knowledge documents.
8. **Policy APIs** — add list/detail/person/coverage/option endpoints with ownership checks.
9. **Knowledge and RAG** — add versioned documents, chunks, embeddings, and filtered retrieval.
10. **Chat and explainability** — persist conversations, messages, sources, and AI-run metadata.
11. **Authentication** — replace the hard-coded test user with JWT or OIDC authentication.
12. **Core-system simulation** — import authoritative insurance data through DTOs and mapping code.

---

# Definition of Done for Every Future Schema Task

Use this order:

```text
1. Confirm domain rules
2. Update ORM models
3. Create and review migration
4. Migrate or seed data
5. Update repository
6. Update service
7. Update API schema and endpoint
8. Add tests
9. Verify API and database
10. Update this task file
```

Never add a table and immediately connect it to the AI layer. Each database and API layer must work independently first.
