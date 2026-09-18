"""
Loads and validates a prepared structured knowledge JSON document.
"""

import json
from pathlib import Path

from app.schemas.structured_knowledge import StructuredKnowledgeDocument


class StructuredKnowledgeLoader:

    def load(self, file_path: str) -> StructuredKnowledgeDocument:
        path = Path(file_path)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return StructuredKnowledgeDocument.model_validate(data)