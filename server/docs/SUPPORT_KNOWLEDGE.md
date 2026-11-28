# Support knowledge indexing

The existing chat searches support procedures in the separate
`support_knowledge_documents` and `support_knowledge_chunks` tables.
Each procedure gets one or more 384-dimensional multilingual E5 embeddings.
The search text includes its title, scenario, intent tag, question variations,
and conditions. Long question lists are split into bounded search chunks with
the same procedure ID. The full validated procedure is stored with the record and
returned after a search match, so a question variation is never answer evidence
by itself.

From `server/`, apply the database migration, then ingest the directory:

```powershell
alembic upgrade head
python -m scripts.ingest_support_knowledge
```

To add support knowledge, put another `*.json` collection in
`data/knowledge/support/processed/`. Give every procedure a unique `id`,
include Czech question variations, and rerun the same ingestion command.
Existing IDs are updated and their embeddings are replaced. The command
validates all files and creates all embeddings before changing database rows;
a failed transaction rolls back. Use `--directory PATH` to index a different
prepared directory.

The existing frontend and chat API need no new endpoint. In development,
`SUPPORT_INCLUDE_DRAFTS=true` lets internal chat use the draft corpus and
retains each procedure's review status in the answer context. Set it to
`false` to enforce the publication gate. Production defaults to `false`.
