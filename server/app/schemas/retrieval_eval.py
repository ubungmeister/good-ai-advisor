"""
Pydantic models for retrieval evaluation datasets.

These models describe:
- one retrieval test case
- the complete evaluation dataset
"""

from pydantic import BaseModel, Field


class RetrievalEvalCase(BaseModel):
    """
    Represents one retrieval evaluation question.

    Example:

    question:
        "Je moje zavazadlo pojištěné proti krádeži?"

    expected_articles:
        [35]

    During evaluation we will check whether
    one of the expected articles appears
    in the retrieved top-k results.
    """

    # Stable identifier used in logs and reports.
    #
    # Example:
    # "baggage_theft"
    id: str

    # Logical category.
    #
    # Useful later for analysing retrieval quality
    # separately for baggage, assistance, liability, etc.
    category: str

    # Language of the user question.
    #
    # Currently mostly:
    # "cs"
    #
    # Later we can add:
    # "en", "ru", ...
    language: str

    # Natural-language question that will be sent
    # to RetrievalService.
    question: str

    # One or more articles that we consider correct.
    #
    # Example:
    # [35]
    #
    # Or potentially:
    # [35, 36]
    expected_articles: list[int] = Field(
        min_length=1
    )


class RetrievalEvalDataset(BaseModel):
    """
    Complete retrieval evaluation dataset
    for one knowledge document.
    """

    # Which knowledge document this dataset belongs to.
    #
    # Example:
    # "VPP_CP_2021"
    document_code: str

    # All evaluation questions.
    cases: list[RetrievalEvalCase] = Field(
        min_length=1
    )