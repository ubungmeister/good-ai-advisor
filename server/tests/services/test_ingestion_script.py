import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import embedding_service
from scripts import ingest_vpp_cp_2021 as ingestion


class FakeEmbeddings:
    def count_document_tokens(self, text):
        return len(text.split()) + 3

    def embed_documents(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]


def prepare_ingestion(monkeypatch):
    db = Mock()
    version = SimpleNamespace(id=uuid4(), version="TEST")
    db.get.return_value = version
    db.execute.return_value.scalar_one_or_none.return_value = None

    def assign_id():
        db.add.call_args.args[0].id = uuid4()

    db.flush.side_effect = assign_id
    monkeypatch.setattr(ingestion, "SessionLocal", lambda: db)
    monkeypatch.setattr(embedding_service, "EmbeddingService", FakeEmbeddings)
    monkeypatch.setattr(sys, "argv", ["ingest", "--product-version-id", str(version.id)])
    return db, version


def test_real_source_reaches_persistence_with_complete_metadata(monkeypatch):
    db, version = prepare_ingestion(monkeypatch)
    ingestion.main()
    document = db.add.call_args.args[0]
    chunks = db.add_all.call_args.args[0]
    assert document.product_version_id == version.id
    assert document.ingestion_status.value == "READY"
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.document_id == document.id for chunk in chunks)
    assert all(len(chunk.embedding) == 384 and chunk.content.strip() for chunk in chunks)
    assert all(chunk.chunk_metadata["token_count"] <= ingestion.MAX_TOKENS for chunk in chunks)
    assert all(chunk.page_number == chunk.chunk_metadata["source_pages"][0] for chunk in chunks)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_embedding_mismatch_rolls_back_before_replacing_existing_data(monkeypatch):
    db, _version = prepare_ingestion(monkeypatch)
    monkeypatch.setattr(FakeEmbeddings, "embed_documents", lambda self, texts: [])
    with pytest.raises(ValueError, match="count mismatch"):
        ingestion.main()
    db.execute.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


@pytest.mark.parametrize("module", [
    "scripts.ingest_vpp_cp_2021", "scripts.run_retrieval_eval",
    "scripts.test_real_retrieval", "scripts.test_retrieval_latency",
    "scripts.debug_retrieval_query", "scripts.validate_chunking",
])
def test_script_entry_points_support_help_without_models_or_database_access(module):
    result = subprocess.run(
        [sys.executable, "-B", "-m", module, "--help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
