from sentence_transformers import SentenceTransformer


class EmbeddingService:

    def __init__(self):
        self.model = SentenceTransformer(
            "intfloat/multilingual-e5-small"
        )

    def embed_document(
        self,
        text: str,
    ) -> list[float]:

        embedding = self.model.encode(
            f"passage: {text}",
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def embed_query(
        self,
        text: str,
    ) -> list[float]:

        embedding = self.model.encode(
            f"query: {text}",
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def count_document_tokens(self, text: str) -> int:
        tokens = self.model.tokenizer(
            f"passage: {text}",
            add_special_tokens=True,
            truncation=False,
        )["input_ids"]

        return len(tokens)

    def embed_documents(
            self,
            texts: list[str],
    ) -> list[list[float]]:
        """
        Creates embeddings for multiple document chunks at once.

        Every document is prefixed with "passage:"
        because E5 was trained to distinguish passages
        from search queries.

        Input:
            [
                "first chunk text",
                "second chunk text",
            ]

        Output:
            [
                [384 floats],
                [384 floats],
            ]
        """

        prepared_texts = [
            f"passage: {text}"
            for text in texts
        ]

        embeddings = self.model.encode(
            prepared_texts,
            normalize_embeddings=True,
        )

        return embeddings.tolist()