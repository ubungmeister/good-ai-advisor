from app.services.structured_knowledge_loader import (
    StructuredKnowledgeLoader,
)


def main():
    loader = StructuredKnowledgeLoader()

    document = loader.load(
        "data/knowledge/processed/vpp_cp_2021_structured.json"
    )

    print(f"Document: {document.document.document_code}")
    print(f"Parts: {len(document.parts)}")

    article_count = sum(
        len(part.articles)
        for part in document.parts
    )

    print(f"Articles: {article_count}")

    for part in document.parts:
        print(
            f"PART {part.code}: "
            f"{part.title} "
            f"({len(part.articles)} articles)"
        )


if __name__ == "__main__":
    main()