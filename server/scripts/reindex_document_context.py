"""Rebuild one resolved public document's vectors; dry-run unless --apply is given."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.models.document_chunk import DocumentChunk
from app.services.document_context import EMBEDDING_FORMAT, prepare_embedding_texts
from app.services.embedding_service import EMBEDDING_MODEL_NAME


def reindex(db, document, embedding_service, *, apply=False, backup_file=None):
    if apply and backup_file is None:
        raise ValueError("Applying an index update requires a backup file")
    query = select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index)
    if apply:
        query = query.with_for_update()
    chunks = list(db.scalars(query).all())
    if not chunks:
        raise ValueError("Document has no chunks")
    texts = prepare_embedding_texts(chunks, embedding_service)
    embeddings = embedding_service.embed_documents(texts)
    if len(embeddings) != len(chunks) or any(
        len(vector) != 384 or not all(math.isfinite(float(value)) for value in vector)
        or not any(float(value) != 0 for value in vector)
        for vector in embeddings
    ):
        raise ValueError("Invalid embedding count, dimension or values")
    plan = {"document_id": str(document.id), "chunks": len(chunks), "format": EMBEDDING_FORMAT,
            "max_tokens": max(embedding_service.count_document_tokens(text) for text in texts),
            "input_sha256": hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest(),
            "applied": apply}
    if apply:
        backup = {"plan": plan, "model": EMBEDDING_MODEL_NAME,
                  "chunks": [{"id": str(chunk.id), "metadata": chunk.chunk_metadata,
                              "embedding": list(map(float, chunk.embedding)) if chunk.embedding is not None else None}
                             for chunk in chunks]}
        backup_file = Path(backup_file)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        # Back up before any assignment and refuse to overwrite another backup.
        with backup_file.open("x", encoding="utf-8") as target:
            json.dump(backup, target, ensure_ascii=False)
        try:
            for chunk, vector in zip(chunks, embeddings, strict=True):
                chunk.embedding = vector
                chunk.chunk_metadata = {**(chunk.chunk_metadata or {}), "embedding_format": EMBEDDING_FORMAT,
                                        "embedding_model": EMBEDDING_MODEL_NAME}
            db.commit()
        except Exception:
            db.rollback()
            raise
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-version-id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-file", type=Path)
    args = parser.parse_args()
    if args.apply and (args.backup_file is None or args.backup_file.exists()):
        parser.error("--apply requires a new --backup-file path")
    from app.db.database import SessionLocal
    from app.services.embedding_service import EmbeddingService
    from scripts.retrieval_scope import resolve_document_scope

    with SessionLocal() as db:
        try:
            if not args.apply:
                db.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
            document = resolve_document_scope(db, "VPP_CP_2021", args.product_version_id)
            plan = reindex(db, document, EmbeddingService(), apply=args.apply, backup_file=args.backup_file)
            print(json.dumps(plan, indent=2))
        except Exception:
            db.rollback()
            raise
        finally:
            db.rollback()


if __name__ == "__main__":
    main()
