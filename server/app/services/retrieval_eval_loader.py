"""
Loads and validates retrieval evaluation datasets.
"""

import json
from pathlib import Path

from app.schemas.retrieval_eval import (
    RetrievalEvalDataset,
)


class RetrievalEvalLoader:
    """
    Loads retrieval evaluation JSON files
    and validates them using Pydantic.
    """

    def load(
        self,
        file_path: str,
    ) -> RetrievalEvalDataset:
        """
        Read the JSON file and convert it
        into a validated RetrievalEvalDataset.
        """

        path = Path(file_path)

        # Fail early if the file does not exist.
        if not path.exists():
            raise FileNotFoundError(
                f"Retrieval eval file not found: {file_path}"
            )

        # Read raw JSON.
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        # Validate JSON structure and types.
        #
        # dict
        #   ↓
        # Pydantic
        #   ↓
        # RetrievalEvalDataset
        return RetrievalEvalDataset.model_validate(
            data
        )