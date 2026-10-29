from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.repositories.message_repository import MessageRepository


def test_get_recent_messages_returns_chronological_order():
    db = Mock()

    oldest = Mock()
    middle = Mock()
    newest = Mock()

    # Simulate the database's newest-first result.
    db.scalars.return_value.all.return_value = [
        newest,
        middle,
        oldest,
    ]

    repository = MessageRepository()

    result = repository.get_recent_by_conversation(
        db=db,
        conversation_id=uuid4(),
        limit=3,
    )

    assert result == [oldest, middle, newest]

    statement = db.scalars.call_args.args[0]
    assert statement._limit_clause.value == 3


def test_get_recent_messages_rejects_non_positive_limit():
    repository = MessageRepository()

    with pytest.raises(ValueError, match="limit must be positive"):
        repository.get_recent_by_conversation(
            db=Mock(),
            conversation_id=uuid4(),
            limit=0,
        )