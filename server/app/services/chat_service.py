from app.services.critical_flow_service import CriticalFlowService
from sqlalchemy.orm import Session

from app.schemas.safety import SafetyRoute
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService
from app.services.safety_classifier import SafetyClassifier
from app.services.safety_router import SafetyRouter
from app.services.critical_flow_service import CriticalFlowService

class ChatService:

    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
        safety_classifier: SafetyClassifier,
        safety_router: SafetyRouter,
        critical_flow_service: CriticalFlowService,

    ):
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service
        self.safety_classifier = safety_classifier
        self.safety_router = safety_router
        self.critical_flow_service = critical_flow_service
    async def generate_answer(
        self,
        *,
        db: Session,
        message: str,
    ) -> str:

        # 1. Analyze safety before running the normal insurance flow.
        safety_decision = await self.safety_classifier.classify(
            message=message,
        )

        # 2. Deterministically decide which flow should handle the request.
        safety_route = self.safety_router.route(
            decision=safety_decision,
        )

        # 3. Critical requests must not continue through the normal RAG flow.
        if safety_route == SafetyRoute.CRITICAL_FLOW:
            return self.critical_flow_service.handle(
                decision=safety_decision,
            )

        # 4. NORMAL_FLOW continues through the existing RAG pipeline.
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
- Do not add examples, interpretations, terminology, procedures, limits,
  or assumptions that are not explicitly present in the provided documentation.
- Preserve the meaning of who must do what and to whom.
- Clearly distinguish mandatory requirements from optional information.
- If the documentation truly does not contain enough information, say so.
- Answer in the same language as the user.
"""

        return await self.llm_service.generate_answer(
            system_prompt=system_prompt,
            user_message=message,
            context=context,
        )
