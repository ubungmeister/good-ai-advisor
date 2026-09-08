from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk
    from app.models.message import Message
    from app.models.policy_coverage import PolicyCoverage
    from app.models.policy_option import PolicyOption


class MessageSource(Base):
    __tablename__ = "message_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id"),
        nullable=True,
    )

    policy_coverage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_coverages.id"),
        nullable=True,
    )

    policy_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_options.id"),
        nullable=True,
    )

    relevance_score: Mapped[Decimal | None] = mapped_column(
        Numeric(),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    message: Mapped[Message] = relationship()

    document_chunk: Mapped[DocumentChunk | None] = relationship()

    policy_coverage: Mapped[PolicyCoverage | None] = relationship()

    policy_option: Mapped[PolicyOption | None] = relationship()