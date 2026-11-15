"""Resolve a document scope explicitly; never guess between product versions."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.models.knowledge_document import DocumentStatus, KnowledgeDocument


def resolve_document_scope(
    db: Session, document_code: str, product_version_id: UUID | None = None,
) -> KnowledgeDocument:
    statement = select(KnowledgeDocument).where(
        KnowledgeDocument.version == document_code,
        KnowledgeDocument.ingestion_status == DocumentStatus.READY,
        exists().where(
            DocumentChunk.document_id == KnowledgeDocument.id,
            DocumentChunk.embedding.is_not(None),
        ),
    )
    if product_version_id is not None:
        statement = statement.where(
            KnowledgeDocument.product_version_id == product_version_id,
        )
    documents = list(db.scalars(statement))
    if not documents:
        raise ValueError(
            f"No READY embedded document {document_code!r} in the requested scope. "
            "Run seed and ingestion first."
        )
    if len(documents) != 1:
        raise ValueError(
            f"Document {document_code!r} is ambiguous. "
            "Pass --product-version-id to select exactly one scope."
        )
    return documents[0]
