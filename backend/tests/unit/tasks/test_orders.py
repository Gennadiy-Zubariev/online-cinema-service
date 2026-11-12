from unittest.mock import MagicMock

import pytest

from src.config.settings import get_settings
from src.tasks import orders
from src.tasks.celery_app import celery_app


def test_delete_expired_pending_orders_task_runs_cleanup_in_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory_mock = MagicMock()
    cleanup_mock = MagicMock()
    monkeypatch.setattr(orders, "SyncSessionLocal", session_factory_mock)
    monkeypatch.setattr(orders, "delete_expired_pending_orders", cleanup_mock)

    orders.delete_expired_pending_orders_task()

    session = session_factory_mock.return_value.__enter__.return_value
    cleanup_mock.assert_called_once_with(session=session, settings=get_settings())


def test_beat_schedule_points_to_registered_task() -> None:
    # The schedule references the task by name; a typo would fail silently.
    task_name = celery_app.conf.beat_schedule["delete-expired-pending-orders"]["task"]

    assert task_name in celery_app.tasks
    assert task_name == orders.delete_expired_pending_orders_task.name
