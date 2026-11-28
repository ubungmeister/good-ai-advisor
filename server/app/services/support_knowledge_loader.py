"""Load the canonical support corpus without making it customer-facing."""

import json
from pathlib import Path

from app.schemas.support_knowledge import (
    SupportKnowledgeCollection,
    SupportProcedure,
)


class SupportKnowledgeLoader:
    def load_file(self, file_path: str | Path) -> SupportKnowledgeCollection:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as file:
            return self.load_data(json.load(file))

    def load_directory(self, directory: str | Path) -> SupportKnowledgeCollection:
        paths = sorted(Path(directory).glob("*.json"))
        if not paths:
            raise ValueError(f"No support knowledge files found in {directory}")

        collections = [self.load_file(path) for path in paths]
        first = collections[0]
        procedures = [procedure for collection in collections for procedure in collection.procedures]
        ids = [procedure.id for procedure in procedures]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate support procedure ID across JSON files")
        if any(collection.language != first.language for collection in collections):
            raise ValueError("Support knowledge files must use one canonical language")
        return first.model_copy(update={"procedures": procedures})

    @staticmethod
    def load_data(data: object) -> SupportKnowledgeCollection:
        if not isinstance(data, dict):
            raise ValueError("Support knowledge must be a JSON object")

        try:
            raw_procedures = data["articles"]
            collection = SupportKnowledgeCollection.model_validate(
                {**data, "procedures": raw_procedures}
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Invalid support knowledge document") from error

        if collection.document_type != "support_knowledge_collection":
            raise ValueError("Unexpected support knowledge document type")
        if any(procedure.document_type != "support_procedure" for procedure in collection.procedures):
            raise ValueError("Support collection contains a non-procedure article")
        return collection
