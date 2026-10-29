from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.conversation_service import ConversationService


def test_recent_messages_require_conversation_ownership():
    service = ConversationService()
    service.conversation_repository = Mock()
    service.message_repository = Mock()

    service.conversation_repository.get_by_id_for_user.return_value = None

    with pytest.raises(
        ValueError,
        match="does not belong to the user",
    ):
        service.get_recent_messages(
            db=Mock(),
            conversation_id=uuid4(),
            user_id=uuid4(),
            limit=10,
        )

    service.message_repository.get_recent_by_conversation.assert_not_called()