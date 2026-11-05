from unittest.mock import MagicMock

import pytest

from src.tasks import accounts
from src.tasks.celery_app import celery_app


def test_delete_expired_tokens_task_runs_cleanup_in_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory_mock = MagicMock()
    cleanup_mock = MagicMock()
    monkeypatch.setattr(accounts, "SyncSessionLocal", session_factory_mock)
    monkeypatch.setattr(accounts, "delete_expired_tokens", cleanup_mock)

    accounts.delete_expired_tokens_task()

    session = session_factory_mock.return_value.__enter__.return_value
    cleanup_mock.assert_called_once_with(session=session)


def test_beat_schedule_points_to_registered_task() -> None:
    # The schedule references the task by name; a typo would fail silently.
    task_name = celery_app.conf.beat_schedule["delete-expired-tokens"]["task"]

    assert task_name in celery_app.tasks
    assert task_name == accounts.delete_expired_tokens_task.name
