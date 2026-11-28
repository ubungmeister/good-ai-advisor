from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SupportPublicationStatus(str, enum.Enum):
    REVIEW_ONLY = "REVIEW_ONLY"
    PUBLISHED = "PUBLISHED"
    SUSPENDED = "SUSPENDED"


class SupportKnowledgeDocument(Base):
    __tablename__ = "support_knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    procedure_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    publication_status: Mapped[SupportPublicationStatus] = mapped_column(
        SqlEnum(SupportPublicationStatus, name="support_publication_status"),
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    applicable_product_versions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    provenance: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retrieval_eligible: Mapped[bool] = mapped_column(nullable=False, default=False)
    document_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    chunks = relationship("SupportKnowledgeChunk", back_populates="document")


class SupportKnowledgeChunk(Base):
    __tablename__ = "support_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_support_chunks_document_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("support_knowledge_documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    searchable_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(384), nullable=True)
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("SupportKnowledgeDocument", back_populates="chunks")
