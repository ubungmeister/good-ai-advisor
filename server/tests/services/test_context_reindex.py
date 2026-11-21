import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.document_context import EMBEDDING_FORMAT, prepare_embedding_texts, reranker_text
from scripts.reindex_document_context import reindex


class Embeddings:
    def count_document_tokens(self, text):
        return len(text.split()) + 3

    def embed_documents(self, texts):
        self.texts = texts
        return [[1.0] + [0.0] * 383 for text in texts]


def fixture():
    document = SimpleNamespace(id=uuid4())
    chunk = SimpleNamespace(id=uuid4(), content="Report the loss.", section_title="Duties",
        chunk_metadata={"part_title": "Baggage insurance", "source_pages": [13]},
        embedding=[0.0, 1.0] + [0.0] * 382)
    db = Mock()
    db.scalars.return_value.all.return_value = [chunk]
    return db, document, chunk, Embeddings()


def test_ingestion_and_stored_rows_have_identical_contextual_input():
    source = SimpleNamespace(content="Report the loss.", part_title="Baggage insurance", article_title="Duties")
    stored = SimpleNamespace(content=source.content, section_title=source.article_title,
                             chunk_metadata={"part_title": source.part_title})
    assert reranker_text(source) == reranker_text(stored)
    assert reranker_text(source) == "Baggage insurance / Duties\nReport the loss."


def test_context_token_overflow_fails_instead_of_truncating():
    source = SimpleNamespace(content="word " * 512, section_title="Heading", chunk_metadata=None)
    with pytest.raises(ValueError, match="truncated"):
        prepare_embedding_texts([source], Embeddings())


def test_dry_run_computes_context_but_does_not_mutate_rows_or_commit():
    db, document, chunk, model = fixture()
    old_vector, old_metadata = list(chunk.embedding), dict(chunk.chunk_metadata)
    plan = reindex(db, document, model)
    assert plan["applied"] is False
    assert model.texts == ["Baggage insurance / Duties\nReport the loss."]
    assert chunk.embedding == old_vector and chunk.chunk_metadata == old_metadata
    db.commit.assert_not_called()


def test_apply_backs_up_prior_values_and_preserves_source_identity(tmp_path):
    db, document, chunk, model = fixture()
    old_id, old_vector, old_metadata = chunk.id, list(chunk.embedding), dict(chunk.chunk_metadata)
    backup_file = tmp_path / "backup.json"
    reindex(db, document, model, apply=True, backup_file=backup_file)
    backup = json.loads(backup_file.read_text(encoding="utf-8"))
    assert backup["chunks"][0]["id"] == str(old_id)
    assert backup["chunks"][0]["embedding"] == old_vector
    assert backup["chunks"][0]["metadata"] == old_metadata
    assert chunk.id == old_id and chunk.content == "Report the loss."
    assert chunk.chunk_metadata["source_pages"] == [13]
    assert chunk.chunk_metadata["embedding_format"] == EMBEDDING_FORMAT
    db.commit.assert_called_once()
    db.add.assert_not_called()
    db.delete.assert_not_called()


def test_existing_backup_is_not_overwritten_and_no_update_occurs(tmp_path):
    db, document, chunk, model = fixture()
    backup = tmp_path / "existing.json"
    backup.write_text("keep this", encoding="utf-8")
    old_vector = list(chunk.embedding)
    with pytest.raises(FileExistsError):
        reindex(db, document, model, apply=True, backup_file=backup)
    assert backup.read_text(encoding="utf-8") == "keep this"
    assert chunk.embedding == old_vector
    db.commit.assert_not_called()


@pytest.mark.parametrize("vectors", [[], [[1.0]], [[0.0] * 384], [[float("nan")] * 384]])
def test_invalid_vectors_are_rejected_before_backing_up_or_updating(tmp_path, vectors):
    db, document, chunk, model = fixture()
    model.embed_documents = lambda texts: vectors
    path = tmp_path / "backup.json"
    old_vector = list(chunk.embedding)
    with pytest.raises(ValueError, match="Invalid embedding"):
        reindex(db, document, model, apply=True, backup_file=path)
    assert not path.exists() and chunk.embedding == old_vector
    db.commit.assert_not_called()


def test_commit_failure_rolls_back_and_keeps_the_backup(tmp_path):
    db, document, chunk, model = fixture()
    db.commit.side_effect = RuntimeError("database error")
    path = tmp_path / "backup.json"
    with pytest.raises(RuntimeError):
        reindex(db, document, model, apply=True, backup_file=path)
    db.rollback.assert_called_once()
    assert path.exists()
