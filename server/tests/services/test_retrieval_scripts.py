from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.schemas.retrieval_eval import RetrievalEvalCase, RetrievalEvalDataset
from scripts.retrieval_scope import resolve_document_scope
from scripts.run_retrieval_eval import evaluate
from scripts.test_retrieval_latency import run_search


def test_eval_keeps_version_scope_and_does_not_credit_another_documents_article():
    document = SimpleNamespace(id=uuid4(), product_version_id=uuid4())
    cases = [RetrievalEvalCase(
        id=name, category="test", language="cs", question=name, expected_articles=[35],
    ) for name in ("hit", "miss")]
    dataset = RetrievalEvalDataset(document_code="VPP_CP_2021", cases=cases)

    class Retrieval:
        def search(self, db, question, limit, *, product_version_id):
            assert product_version_id == document.product_version_id
            if question == "miss":
                return []
            return [
                (SimpleNamespace(document_id=uuid4(), article_number="35"), 1.0),
                (SimpleNamespace(document_id=document.id, article_number=None), 0.9),
                (SimpleNamespace(document_id=document.id, article_number="35"), 0.8),
            ]

    metrics = evaluate(Mock(), Retrieval(), dataset, document)
    assert metrics == {"queries": 2, "hit@1": 0, "hit@3": 0.5, "hit@5": 0.5, "mrr": 1 / 6}


def test_scope_requires_an_unambiguous_ready_embedded_document():
    db = Mock()
    db.scalars.return_value = []
    with pytest.raises(ValueError, match="Run seed and ingestion"):
        resolve_document_scope(db, "VPP_CP_2021")
    db.scalars.return_value = [Mock(), Mock()]
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_document_scope(db, "VPP_CP_2021")
    document = SimpleNamespace(id=uuid4(), product_version_id=uuid4())
    db.scalars.return_value = [document]
    assert resolve_document_scope(db, "VPP_CP_2021", document.product_version_id) is document
    statement = db.scalars.call_args.args[0]
    parameters = statement.compile().params
    assert document.product_version_id in parameters.values()
    assert "VPP_CP_2021" in parameters.values()
    assert "embedding IS NOT NULL" in str(statement)


def test_latency_probe_passes_required_scope():
    version = uuid4()
    retrieval = Mock()
    retrieval.search.return_value = []
    db = Mock()
    run_search(retrieval, db, 1, version)
    assert retrieval.search.call_args.kwargs["product_version_id"] == version
