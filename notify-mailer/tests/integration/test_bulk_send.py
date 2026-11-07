"""Bulk send against the real Notify API using only the test key.

Test keys never deliver email. Run with:

    uv run --env-file ../.env pytest -m integration

Tests in this class run in order and share one reference.
"""

import os
from uuid import uuid4

import pytest

from notify_mailer.campaign import Plan, Result, plan_send, send_all
from notify_mailer.client import NotifyClient
from notify_mailer.render import Message

pytestmark = pytest.mark.integration

RECIPIENTS = [f"bulk-check-{number:03d}@example.com" for number in range(600)]


@pytest.fixture(scope="module")
def client() -> NotifyClient:
    key = os.environ.get("NOTIFY_API_KEY_TEST")
    template_id = os.environ.get("NOTIFY_TEMPLATE_ID")
    if not key or not template_id:
        pytest.skip("NOTIFY_API_KEY_TEST and NOTIFY_TEMPLATE_ID are needed")
    return NotifyClient(key, template_id)


@pytest.fixture(scope="module")
def message() -> Message:
    return Message(
        subject="Integration bulk check",
        body="# Bulk check\n\nSent with the test key. Not delivered.",
        reference=f"integration-bulk-{uuid4().hex[:8]}",
    )


class TestBulkSend:
    def test_first_half_sends(self, client: NotifyClient, message: Message) -> None:
        assert send_all(client, message, RECIPIENTS[:300]) == Result(sent=300)

    def test_full_run_skips_first_half(
        self, client: NotifyClient, message: Message
    ) -> None:
        plan = plan_send(client, message, RECIPIENTS)
        assert (plan.to_send, plan.already_sent) == (RECIPIENTS[300:], 300)
        assert send_all(client, message, plan.to_send) == Result(sent=300)

    def test_third_run_sends_nothing(
        self, client: NotifyClient, message: Message
    ) -> None:
        assert plan_send(client, message, RECIPIENTS) == Plan([], 600)

    def test_every_notification_is_recorded(
        self, client: NotifyClient, message: Message
    ) -> None:
        assert sum(client.status_counts(message.reference).values()) == 600
