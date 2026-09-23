from sentence_transformers import CrossEncoder

from app.models.document_chunk import DocumentChunk


MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class RerankerService:
    def __init__(self):
        self.model = CrossEncoder(
            MODEL_NAME,
            backend="onnx",
            model_kwargs={
                "file_name": "onnx/model_quint8_avx2.onnx",
            },
        )

    def rerank(
        self,
        question: str,
        candidates: list[
            tuple[DocumentChunk, float]
        ],
        limit: int,
    ) -> list[
        tuple[DocumentChunk, float]
    ]:
        if not candidates:
            return []

        pairs = [
            (
                question,
                chunk.content,
            )
            for chunk, _ in candidates
        ]

        scores = self.model.predict(
            pairs,
            batch_size=16,
            show_progress_bar=False,
        )

        reranked = [
            (
                chunk,
                float(score),
            )
            for (chunk, _), score in zip(
                candidates,
                scores,
            )
        ]

        reranked.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return reranked[:limit]