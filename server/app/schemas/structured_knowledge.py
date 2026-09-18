"""
Models for validated structured knowledge documents.
"""

from pydantic import BaseModel


class KnowledgeBlock(BaseModel):
    text: str
    pages: list[int]


class KnowledgeArticle(BaseModel):
    number: int
    start_page: int
    title: str | None
    source_pages: list[int]
    blocks: list[KnowledgeBlock]
    content: str


class KnowledgePart(BaseModel):
    code: str
    title: str
    start_page: int
    end_page: int
    articles: list[KnowledgeArticle]


class KnowledgeDocumentMetadata(BaseModel):
    document_code: str
    source_file: str
    title: str
    insurer: str
    language: str
    document_type: str
    total_pdf_pages: int
    effective_from: str


class StructuredKnowledgeDocument(BaseModel):
    schema_version: str
    document: KnowledgeDocumentMetadata
    parts: list[KnowledgePart]