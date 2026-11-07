from collections import Counter
from collections.abc import Callable

import pytest
from notifications_python_client.errors import HTTPError
from pytest_mock import MockerFixture, MockType

from notify_mailer.client import NotifyClient, is_retryable
from notify_mailer.render import Message

MESSAGE = Message("Subject", "Body", "ref-1")


@pytest.fixture
def api(mocker: MockerFixture) -> MockType:
    return mocker.MagicMock()


@pytest.fixture
def sleep(mocker: MockerFixture) -> MockType:
    return mocker.MagicMock()


@pytest.fixture
def client(api: MockType, sleep: MockType) -> NotifyClient:
    return NotifyClient(
        "key", "template-id", retries=2, wait_seconds=1, api=api, sleep=sleep
    )


class TestIsRetryable:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            pytest.param(400, False, id="bad-request"),
            pytest.param(403, False, id="forbidden"),
            pytest.param(429, True, id="rate-limit"),
            pytest.param(500, True, id="server-error"),
            pytest.param(503, True, id="unavailable"),
        ],
    )
    def test_classifies_status(
        self, http_error: Callable[[int], HTTPError], status: int, expected: bool
    ) -> None:
        assert is_retryable(http_error(status)) is expected


class TestSend:
    def test_sends_subject_body_and_reference(
        self,
        client: NotifyClient,
        api: MockType,
    ) -> None:
        api.send_email_notification.return_value = {"id": "n-1"}
        assert client.send("a@example.com", MESSAGE) == "n-1"
        api.send_email_notification.assert_called_once_with(
            email_address="a@example.com",
            template_id="template-id",
            personalisation={"subject": "Subject", "body": "Body"},
            reference="ref-1",
        )

    def test_retries_with_doubling_wait(
        self,
        http_error: Callable[[int], HTTPError],
        client: NotifyClient,
        api: MockType,
        sleep: MockType,
    ) -> None:
        api.send_email_notification.side_effect = [
            http_error(429),
            http_error(500),
            {"id": "n-1"},
        ]
        assert client.send("a@example.com", MESSAGE) == "n-1"
        assert [call.args[0] for call in sleep.call_args_list] == [1, 2]

    def test_raises_after_last_retry(
        self,
        http_error: Callable[[int], HTTPError],
        client: NotifyClient,
        api: MockType,
    ) -> None:
        api.send_email_notification.side_effect = http_error(500)
        with pytest.raises(HTTPError):
            client.send("a@example.com", MESSAGE)
        assert api.send_email_notification.call_count == 3

    def test_does_not_retry_rejections(
        self,
        http_error: Callable[[int], HTTPError],
        client: NotifyClient,
        api: MockType,
        sleep: MockType,
    ) -> None:
        api.send_email_notification.side_effect = http_error(400)
        with pytest.raises(HTTPError):
            client.send("a@example.com", MESSAGE)
        sleep.assert_not_called()


class TestSentAddresses:
    def test_returns_normalised_addresses(
        self,
        client: NotifyClient,
        api: MockType,
    ) -> None:
        api.get_all_notifications_iterator.return_value = iter(
            [{"email_address": "A@Example.com"}, {"email_address": "b@example.com"}]
        )
        assert client.sent_addresses("ref-1") == {"a@example.com", "b@example.com"}
        api.get_all_notifications_iterator.assert_called_once_with(
            template_type="email", reference="ref-1"
        )


class TestStatusCounts:
    def test_counts_each_status(
        self,
        client: NotifyClient,
        api: MockType,
    ) -> None:
        api.get_all_notifications_iterator.return_value = iter(
            [{"status": "delivered"}, {"status": "delivered"}, {"status": "sending"}]
        )
        assert client.status_counts("ref-1") == Counter(delivered=2, sending=1)
