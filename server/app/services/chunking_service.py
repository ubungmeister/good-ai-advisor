from sqlalchemy.orm import Session

from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService


class ChatService:

    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
    ):
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

    async def generate_answer(
        self,
        *,
        db: Session,
        message: str,
    ) -> str:

        retrieval_results = self.retrieval_service.search(
            db=db,
            question=message,
            limit=5,
        )

        context = "\n\n".join(
            f"[DOCUMENT {index}]\n{chunk.content}"
            for index, (chunk, _score) in enumerate(
                retrieval_results,
                start=1,
            )
        )

        system_prompt = """
        You are an insurance assistant.

        Answer the user's question strictly from the provided insurance documentation.

        Rules:
        - Read all provided document excerpts carefully.
        - If any excerpt directly answers the question, use it.
        - Do not ignore relevant information just because other excerpts are unrelated.
        - Do not add examples, interpretations, terminology, procedures, limits, or assumptions that are not explicitly present in the provided documentation.
        - Preserve the meaning of who must do what and to whom.
        - Clearly distinguish mandatory requirements from optional information.
        - If the documentation truly does not contain enough information, say so.
        - Answer in the same language as the user.
        """

        answer = await self.llm_service.generate_answer(
            system_prompt=system_prompt,
            user_message=message,
            context=context,
        )

        return answer