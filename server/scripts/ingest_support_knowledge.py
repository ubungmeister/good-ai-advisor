"""Ingest the prepared support knowledge JSON files into PostgreSQL.

Pipeline:

support JSON files
    -> validation
    -> search chunks
    -> embeddings
    -> SupportKnowledgeDocument rows (complete procedures)
    -> SupportKnowledgeChunk rows (searchable text)
    -> PostgreSQL / pgvector

Run after migrations: python -m scripts.ingest_support_knowledge

The script is safe to run repeatedly: existing procedure IDs are updated,
and their search chunks and embeddings are deleted and recreated.
"""

import argparse
import json
from datetime import datetime, time
from pathlib import Path

from sqlalchemy import delete, select

from app.db.database import SessionLocal
from app.models.support_knowledge_document import (
    SupportKnowledgeChunk, SupportKnowledgeDocument, SupportPublicationStatus,
)
from app.schemas.support_knowledge import SupportProcedure
from app.services.support_knowledge_loader import SupportKnowledgeLoader


DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data/knowledge/support/processed"


def search_chunks(procedure: SupportProcedure, embedding_service) -> list[str]:
    """Keep every question variation inside the embedding model's token budget."""
    base = "\n".join(filter(None, [
        procedure.title, procedure.scenario, procedure.intent_tag, *procedure.conditions,
    ]))
    if embedding_service.count_document_tokens(base) > 400:
        raise ValueError(f"Support procedure {procedure.id} has an oversized search header")
    chunks = []
    current = base
    for question in procedure.question_variations:
        candidate = current + "\n" + question
        if embedding_service.count_document_tokens(candidate) <= 400:
            current = candidate
            continue
        chunks.append(current)
        current = base + "\n" + question
        if embedding_service.count_document_tokens(current) > 400:
            raise ValueError(f"Support procedure {procedure.id} has an oversized question variation")
    chunks.append(current)
    return chunks


def ingest(directory: Path, *, db, embedding_service) -> int:
    collection = SupportKnowledgeLoader().load_directory(directory)
    procedures = collection.procedures
    records = [
        (procedure, index, text)
        for procedure in procedures
        for index, text in enumerate(search_chunks(procedure, embedding_service))
    ]
    texts = [text for _, _, text in records]
    embeddings = embedding_service.embed_documents(texts)
    if len(embeddings) != len(records) or any(len(vector) != 384 for vector in embeddings):
        raise ValueError("Support search chunk / 384-dimensional embedding count mismatch")
    records_by_id: dict[str, list[tuple[int, str, list[float]]]] = {}
    for (procedure, index, search_text), embedding in zip(records, embeddings, strict=True):
        records_by_id.setdefault(procedure.id, []).append((index, search_text, embedding))

    try:
        for procedure in procedures:
            document = db.scalar(
                select(SupportKnowledgeDocument).where(
                    SupportKnowledgeDocument.procedure_id == procedure.id
                )
            )
            is_new_document = document is None
            if is_new_document:
                document = SupportKnowledgeDocument(procedure_id=procedure.id)
                db.add(document)
            else:
                db.execute(delete(SupportKnowledgeChunk).where(
                    SupportKnowledgeChunk.document_id == document.id
                ))

            document.title = procedure.title
            document.language = procedure.language
            document.category = procedure.category
            document.publication_status = SupportPublicationStatus(procedure.publication_status)
            document.review_status = procedure.review_status
            document.reviewed_by = procedure.reviewed_by
            document.approved_at = (
                datetime.combine(procedure.approved_at, time.min)
                if procedure.approved_at else None
            )
            document.effective_from = procedure.effective_from
            document.effective_to = procedure.effective_to
            document.applicable_product_versions = procedure.applicable_policy_versions
            document.provenance = procedure.source_ids
            document.retrieval_eligible = procedure.retrieval_eligible
            document.document_metadata = {"procedure": procedure.model_dump(mode="json")}
            if is_new_document:
                db.flush()
            for index, search_text, embedding in records_by_id[procedure.id]:
                db.add(SupportKnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    searchable_text=search_text,
                    evidence_text=json.dumps(procedure.model_dump(mode="json"), ensure_ascii=False),
                    embedding=embedding,
                    chunk_metadata={"embedding_model": "intfloat/multilingual-e5-small"},
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(procedures)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed and ingest support JSON files.")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    from app.services.embedding_service import EmbeddingService

    db = SessionLocal()
    try:
        count = ingest(args.directory, db=db, embedding_service=EmbeddingService())
        print(f"Indexed {count} support procedures from {args.directory}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
