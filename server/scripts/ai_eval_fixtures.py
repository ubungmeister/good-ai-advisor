"""Synthetic policy and in-memory persistence; never seed or change a database."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from app.schemas.query_plan import TaskType
from app.schemas.task_result import PolicyTaskContent, TaskResult, RetrievalTaskContent, RetrievedChunk
from app.schemas.task_routing import TaskTarget

SOURCE = Path(__file__).resolve().parents[1] / "data/knowledge/processed/vpp_cp_2021_structured.json"
USER_ID = UUID("00000000-0000-0000-0000-000000000001")
POLICY_ID = UUID("00000000-0000-0000-0000-000000000002")
VERSION_ID = UUID("00000000-0000-0000-0000-000000000003")
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000004")


def policy_fixture():
    return PolicyTaskContent.model_validate({
        "policy": {
            "id": str(POLICY_ID), "policy_number": "EVAL-SYNTHETIC-001",
            "policy_status": "ACTIVE", "payment_status": "PAID",
            "start_date": "2026-09-01", "end_date": "2026-09-15",
            "premium_amount": "1290.00", "currency": "CZK", "paid_at": None,
        },
        "coverages": [{
            "id": "00000000-0000-0000-0000-000000000005",
            "limit_amount": "100000.00", "currency": "CZK",
            "coverage_type": {"code": "BAGGAGE", "name": "Baggage"},
        }],
        "options": [], "people": [], "travel_details": None,
    })


def source_articles():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    return {a["number"]: (part, a) for part in source["parts"] for a in part["articles"]}


def article_chunks(numbers):
    articles = source_articles()
    return [RetrievedChunk(
        id=uuid5(NAMESPACE_URL, f"ai-eval/VPP_CP_2021/{number}"),
        document_id=DOCUMENT_ID, content=articles[number][1]["content"], score=1.0,
        article_number=str(number), section_title=articles[number][1]["title"],
        page_number=articles[number][1]["source_pages"][0],
    ) for number in numbers]


def task_results(case):
    results = []
    if case.use_policy:
        results.append(TaskResult(task_type=TaskType.POLICY_DETAILS,
                                  target=TaskTarget.POLICY, content=policy_fixture()))
    if case.articles:
        results.append(TaskResult(task_type=TaskType.GENERAL_QUESTION,
                                  target=TaskTarget.RETRIEVAL,
                                  content=RetrievalTaskContent(chunks=article_chunks(case.articles))))
    return results


class FixturePolicyService:
    def __init__(self, use_policy=True, product_version_id=VERSION_ID):
        self.use_policy = use_policy
        self.product_version_id = product_version_id

    def get_policy_for_user(self, *, db, policy_id, user_id):
        if user_id != USER_ID or policy_id != POLICY_ID:
            return None
        return SimpleNamespace(product_version_id=self.product_version_id)

    def get_policy_details_for_user(self, *, db, policy_id, user_id):
        if not self.use_policy or self.get_policy_for_user(
            db=db, policy_id=policy_id, user_id=user_id,
        ) is None:
            return None
        return policy_fixture()


class FixtureRetrieval:
    """Oracle evidence for isolating generation; explicitly not retrieval evaluation."""
    def __init__(self, articles):
        self.articles = articles

    def search(self, *, db, question, limit, product_version_id):
        return [(chunk, chunk.score) for chunk in article_chunks(self.articles)[:limit]]


class MemoryConversations:
    def __init__(self):
        self.conversation = SimpleNamespace(id=uuid4(), policy_id=POLICY_ID)
        self.messages = []

    def get_or_create(self, **kwargs):
        return self.conversation

    def get_recent_messages(self, *, limit, **kwargs):
        return self.messages[-limit:]

    def add_message(self, *, role, content, **kwargs):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        self.messages.append(message)
        return message


class MemorySink:
    def save_from_task_results(self, **kwargs):
        pass

    def save_run(self, **kwargs):
        pass
