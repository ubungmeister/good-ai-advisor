import uuid
from unittest.mock import Mock

from app.models.policy import Policy
from app.services.policy_service import PolicyService


def test_get_policy_for_owner():
    service = PolicyService()

    repository = Mock()
    service.policy_repository = repository

    user_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    policy = Policy(
        id=policy_id,
        owner_user_id=user_id,
        policy_number="TI-TEST-001",
    )

    repository.get_by_id.return_value = policy

    result = service.get_policy_for_user(
        db=Mock(),
        policy_id=policy_id,
        user_id=user_id,
    )

    assert result == policy

def test_get_policy_for_wrong_user_returns_none():
    service = PolicyService()

    repository = Mock()
    service.policy_repository = repository

    owner_id = uuid.uuid4()
    another_user_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    policy = Policy(
        id=policy_id,
        owner_user_id=owner_id,
        policy_number="TI-TEST-001",
    )

    repository.get_by_id.return_value = policy

    result = service.get_policy_for_user(
        db=Mock(),
        policy_id=policy_id,
        user_id=another_user_id,
    )

    assert result is None

def test_get_policy_not_found_returns_none():
    service = PolicyService()

    repository = Mock()
    service.policy_repository = repository

    repository.get_by_id.return_value = None

    result = service.get_policy_for_user(
        db=Mock(),
        policy_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    assert result is None