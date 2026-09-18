"""
Ingests the prepared VPP CP 2021 knowledge document into PostgreSQL.

Pipeline:

structured JSON
    -> validation
    -> chunking
    -> embeddings
    -> KnowledgeDocument
    -> DocumentChunk rows
    -> PostgreSQL / pgvector

The script is safe to run repeatedly:
existing chunks for this document are deleted and recreated.
"""

from datetime import date

from sqlalchemy import delete, select

from app.db.database import SessionLocal

from app.models.document_chunk import DocumentChunk
from app.models.knowledge_document import (
    DocumentStatus,
    KnowledgeDocument,
)
from app.models.product_version import ProductVersion

from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.structured_knowledge_loader import (
    StructuredKnowledgeLoader,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

STRUCTURED_FILE_PATH = (
    "data/knowledge/processed/"
    "vpp_cp_2021_structured.json"
)

SOURCE_FILE_NAME = "11N9393_VPP_CP_2021.pdf"

DOCUMENT_CODE = "VPP_CP_2021"

# For our current DEV environment we simply attach
# the document to the existing synthetic product version.
PRODUCT_VERSION = "2026.1"

MAX_TOKENS = 400


def main():
    db = SessionLocal()

    try:
        print("=== VPP CP 2021 INGESTION ===")
        print()

        # ---------------------------------------------------------
        # 1. Load the prepared structured JSON.
        # ---------------------------------------------------------

        print("Loading structured document...")

        loader = StructuredKnowledgeLoader()

        structured_document = loader.load(
            STRUCTURED_FILE_PATH
        )

        print(
            f"Loaded: "
            f"{structured_document.document.document_code}"
        )

        # ---------------------------------------------------------
        # 2. Initialize embedding model.
        #
        # The same service is used for:
        # - exact token counting
        # - creating embeddings
        # ---------------------------------------------------------

        print("Loading embedding model...")

        embedding_service = EmbeddingService()

        # ---------------------------------------------------------
        # 3. Create chunks <= 400 tokens.
        # ---------------------------------------------------------

        print("Creating chunks...")

        chunking_service = ChunkingService(
            embedding_service=embedding_service,
            max_tokens=MAX_TOKENS,
        )

        chunks = chunking_service.create_chunks(
            structured_document
        )

        print(
            f"Chunks created: {len(chunks)}"
        )

        # ---------------------------------------------------------
        # 4. Create one embedding for every chunk.
        #
        # Example:
        #
        # chunk 0 -> vector[384]
        # chunk 1 -> vector[384]
        # chunk 2 -> vector[384]
        # ---------------------------------------------------------

        print("Creating embeddings...")

        texts = [
            chunk.content
            for chunk in chunks
        ]

        embeddings = embedding_service.embed_documents(
            texts
        )

        # Defensive check:
        #
        # every chunk must have exactly one embedding.
        if len(chunks) != len(embeddings):
            raise ValueError(
                "Chunk / embedding count mismatch: "
                f"{len(chunks)} chunks, "
                f"{len(embeddings)} embeddings"
            )

        print(
            f"Embeddings created: {len(embeddings)}"
        )

        # ---------------------------------------------------------
        # 5. Find our existing DEV ProductVersion.
        #
        # IMPORTANT:
        #
        # VPP CP 2021 is still the document version.
        #
        # ProductVersion 2026.1 is only our current synthetic
        # development relation.
        # ---------------------------------------------------------

        print(
            f"Finding ProductVersion {PRODUCT_VERSION}..."
        )

        product_version = db.scalar(
            select(ProductVersion)
            .where(
                ProductVersion.version
                == PRODUCT_VERSION
            )
        )

        if product_version is None:
            raise ValueError(
                f"ProductVersion "
                f"'{PRODUCT_VERSION}' was not found."
            )

        print(
            f"ProductVersion found: "
            f"{product_version.version}"
        )

        # ---------------------------------------------------------
        # 6. Find or create KnowledgeDocument.
        #
        # KnowledgeDocument represents the whole source PDF.
        #
        # DocumentChunk represents searchable pieces
        # of that document.
        # ---------------------------------------------------------

        knowledge_document = db.scalar(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.product_version_id
                == product_version.id,

                KnowledgeDocument.version
                == DOCUMENT_CODE,
            )
        )

        if knowledge_document is None:
            print(
                "Creating KnowledgeDocument..."
            )

            knowledge_document = KnowledgeDocument(
                product_version_id=product_version.id,

                title=(
                    structured_document
                    .document
                    .title
                ),

                document_type="VPP",

                version=DOCUMENT_CODE,

                language=(
                    structured_document
                    .document
                    .language
                ),

                effective_from=date(
                    2021,
                    4,
                    1,
                ),

                effective_to=None,

                authority_rank=1,

                file_name=SOURCE_FILE_NAME,

                storage_uri=(
                    "data/knowledge/raw/"
                    + SOURCE_FILE_NAME
                ),

                source_url=None,

                checksum=None,

                ingestion_status=(
                    DocumentStatus.PROCESSING
                ),
            )

            db.add(
                knowledge_document
            )

            # We need the ID before creating DocumentChunks.
            db.flush()

            print(
                f"KnowledgeDocument created: "
                f"{knowledge_document.id}"
            )

        else:
            print(
                f"KnowledgeDocument found: "
                f"{knowledge_document.id}"
            )

            knowledge_document.ingestion_status = (
                DocumentStatus.PROCESSING
            )

        # ---------------------------------------------------------
        # 7. Delete old chunks.
        #
        # This makes the ingestion script repeatable.
        #
        # If we change chunking logic and run again,
        # we do not create duplicate chunks.
        # ---------------------------------------------------------

        print("Removing old chunks...")

        db.execute(
            delete(DocumentChunk)
            .where(
                DocumentChunk.document_id
                == knowledge_document.id
            )
        )

        # ---------------------------------------------------------
        # 8. Convert KnowledgeChunk objects into
        #    SQLAlchemy DocumentChunk rows.
        # ---------------------------------------------------------

        print("Saving chunks to database...")

        document_chunks: list[DocumentChunk] = []

        for global_index, (
            chunk,
            embedding,
        ) in enumerate(
            zip(
                chunks,
                embeddings,
                strict=True,
            )
        ):
            # page_number in our DB model contains
            # one primary page.
            #
            # Full page information remains available
            # inside chunk_metadata.
            page_number = (
                chunk.source_pages[0]
                if chunk.source_pages
                else None
            )

            # section_title should be useful to humans.
            #
            # Prefer article title.
            # If article has no title, use part title.
            section_title = (
                chunk.article_title
                or chunk.part_title
            )

            section_path = (
                f"Part {chunk.part_code}"
                f" > Article {chunk.article_number}"
            )

            document_chunk = DocumentChunk(
                document_id=knowledge_document.id,

                # IMPORTANT:
                #
                # Database chunk_index must be unique
                # across the WHOLE document.
                #
                # Therefore we use global_index here,
                # not chunk.chunk_index.
                chunk_index=global_index,

                page_number=page_number,

                # Our DB model stores this as string.
                article_number=str(
                    chunk.article_number
                ),

                section_title=section_title,

                section_path=section_path,

                # We do not assign coverage automatically yet.
                # Later this can be classified/enriched.
                coverage_code=None,

                content=chunk.content,

                embedding=embedding,

                # Additional structured information
                # that may be useful later for filtering,
                # debugging and citations.
                chunk_metadata={
                    "document_code": (
                        chunk.document_code
                    ),

                    "part_code": (
                        chunk.part_code
                    ),

                    "part_title": (
                        chunk.part_title
                    ),

                    "article_number": (
                        chunk.article_number
                    ),

                    "article_title": (
                        chunk.article_title
                    ),

                    "source_pages": (
                        chunk.source_pages
                    ),

                    # This index is local inside
                    # the original article.
                    "article_chunk_index": (
                        chunk.chunk_index
                    ),

                    "token_count": (
                        chunk.token_count
                    ),
                },
            )

            document_chunks.append(
                document_chunk
            )

        # add_all sends all ORM objects
        # to the current SQLAlchemy session.
        db.add_all(
            document_chunks
        )

        # ---------------------------------------------------------
        # 9. Mark document as ready.
        # ---------------------------------------------------------

        knowledge_document.ingestion_status = (
            DocumentStatus.READY
        )

        # ---------------------------------------------------------
        # 10. Commit everything as one transaction.
        # ---------------------------------------------------------

        db.commit()

        print()
        print("=== INGESTION COMPLETE ===")
        print()

        print(
            f"Document: {DOCUMENT_CODE}"
        )

        print(
            f"Document ID: "
            f"{knowledge_document.id}"
        )

        print(
            f"Chunks saved: "
            f"{len(document_chunks)}"
        )

        print(
            "Embedding dimensions: 384"
        )

        print(
            f"Status: "
            f"{knowledge_document.ingestion_status}"
        )

    except Exception:
        # If anything fails, do not leave
        # half-imported data in PostgreSQL.
        db.rollback()

        print()
        print("INGESTION FAILED")

        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()