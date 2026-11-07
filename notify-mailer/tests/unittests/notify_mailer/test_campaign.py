from collections.abc import Callable

import pytest
from notifications_python_client.errors import HTTPError
from pytest_mock import MockerFixture, MockType

from notify_mailer.campaign import Plan, Result, plan_send, send_all
from notify_mailer.render import Message

MESSAGE = Message("Subject", "Body", "ref-1")


@pytest.fixture
def client(mocker: MockerFixture) -> MockType:
    return mocker.MagicMock()


class TestPlanSend:
    def test_skips_addresses_already_sent(self, client: MockType) -> None:
        client.sent_addresses.return_value = {"b@example.com"}
        plan = plan_send(client, MESSAGE, ["a@example.com", "b@example.com"])
        assert plan == Plan(to_send=["a@example.com"], already_sent=1)
        client.sent_addresses.assert_called_once_with("ref-1")

    def test_ignores_sent_addresses_not_on_list(self, client: MockType) -> None:
        client.sent_addresses.return_value = {"z@example.com"}
        assert plan_send(client, MESSAGE, ["a@example.com"]) == Plan(
            ["a@example.com"], 0
        )


class TestSendAll:
    def test_sends_to_every_address(self, client: MockType) -> None:
        assert send_all(client, MESSAGE, ["a@example.com", "b@example.com"]) == Result(
            2, []
        )
        assert client.send.call_count == 2

    def test_carries_on_after_rejection(
        self, http_error: Callable[[int], HTTPError], client: MockType
    ) -> None:
        client.send.side_effect = [http_error(400), "n-2"]
        result = send_all(client, MESSAGE, ["bad@example.com", "b@example.com"])
        assert result == Result(sent=1, failed=["bad@example.com"])

    def test_logs_never_contain_addresses(
        self,
        http_error: Callable[[int], HTTPError],
        client: MockType,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from loguru import logger

        handler = logger.add(caplog.handler, format="{message}")
        client.send.side_effect = [http_error(400), "n-2"]
        send_all(
            client, MESSAGE, ["secret@example.com", "b@example.com"], progress_every=1
        )
        logger.remove(handler)
        assert "example.com" not in caplog.text
        assert "Recipient 1 rejected by Notify (400)" in caplog.text
