from app.services.embedding_service import EmbeddingService
from app.services.structured_knowledge_loader import (
    StructuredKnowledgeLoader,
)


MAX_TOKENS = 400


def main():
    loader = StructuredKnowledgeLoader()
    embedding_service = EmbeddingService()

    document = loader.load(
        "data/knowledge/processed/vpp_cp_2021_structured.json"
    )

    article_sizes = []
    oversized_blocks = []

    total_blocks = 0

    for part in document.parts:
        for article in part.articles:
            article_tokens = embedding_service.count_document_tokens(
                article.content
            )

            article_sizes.append(
                (
                    article_tokens,
                    part.code,
                    article.number,
                    article.title,
                )
            )

            for block_index, block in enumerate(article.blocks):
                total_blocks += 1

                block_tokens = embedding_service.count_document_tokens(
                    block.text
                )

                if block_tokens > MAX_TOKENS:
                    oversized_blocks.append(
                        (
                            block_tokens,
                            part.code,
                            article.number,
                            block_index,
                        )
                    )

    article_sizes.sort(reverse=True)

    print(f"Parts: {len(document.parts)}")
    print(f"Articles: {len(article_sizes)}")
    print(f"Blocks: {total_blocks}")

    print("\nLargest articles:")

    for tokens, part_code, article_number, title in article_sizes[:10]:
        print(
            f"{tokens:>4} tokens | "
            f"Part {part_code} | "
            f"Article {article_number} | "
            f"{title}"
        )

    print("\nOversized blocks (> 400 tokens):")

    if not oversized_blocks:
        print("None")
    else:
        for (
            tokens,
            part_code,
            article_number,
            block_index,
        ) in oversized_blocks:
            print(
                f"{tokens:>4} tokens | "
                f"Part {part_code} | "
                f"Article {article_number} | "
                f"Block {block_index}"
            )


if __name__ == "__main__":
    main()