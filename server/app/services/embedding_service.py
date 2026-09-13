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