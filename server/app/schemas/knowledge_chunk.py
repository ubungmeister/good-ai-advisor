from pydantic import BaseModel


class KnowledgeChunk(BaseModel):
    document_code: str

    part_code: str
    part_title: str

    article_number: int
    article_title: str | None

    source_pages: list[int]

    chunk_index: int
    token_count: int

    content: str