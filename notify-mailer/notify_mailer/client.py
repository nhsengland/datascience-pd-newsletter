"""Thin wrapper around the GOV.UK Notify client for sending emails."""

import time
from collections import Counter
from collections.abc import Callable

from loguru import logger
from notifications_python_client.errors import HTTPError
from notifications_python_client.notifications import NotificationsAPIClient

from notify_mailer.recipients import normalise
from notify_mailer.render import Message


def is_retryable(error: HTTPError) -> bool:
    """Return whether Notify suggests trying the request again.

    Parameters
    ----------
    error : HTTPError
        Error raised by the Notify client.

    Returns
    -------
    bool
        True for rate limits (429) and server errors (5xx).
    """
    return error.status_code == 429 or error.status_code >= 500


class NotifyClient:
    """Send emails through one Notify email template.

    Parameters
    ----------
    api_key : str
        Notify API key. Its type (test, team or live) decides who receives email.
    template_id : str
        Template with ``((subject))`` as its subject and ``((body))`` as its body.
    retries : int
        Attempts after the first for retryable errors.
    wait_seconds : float
        Wait before the first retry. It doubles on each later retry.
    api : NotificationsAPIClient | None
        Client to use instead of building one from ``api_key``.
    sleep : Callable[[float], None]
        Function used to wait between retries.
    """

    def __init__(
        self,
        api_key: str,
        template_id: str,
        retries: int = 3,
        wait_seconds: float = 2.0,
        api: NotificationsAPIClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api = api or NotificationsAPIClient(api_key)
        self.template_id = template_id
        self.retries = retries
        self.wait_seconds = wait_seconds
        self.sleep = sleep

    def send(self, address: str, message: Message) -> str:
        """Send one email, retrying on rate limits and server errors.

        Parameters
        ----------
        address : str
            Recipient address.
        message : Message
            Rendered message.

        Returns
        -------
        str
            Notify notification id.

        Raises
        ------
        HTTPError
            If Notify rejects the email or retries run out.
        """
        for attempt in range(self.retries + 1):
            try:
                response = self.api.send_email_notification(
                    email_address=address,
                    template_id=self.template_id,
                    personalisation={"subject": message.subject, "body": message.body},
                    reference=message.reference,
                )
                return response["id"]
            except HTTPError as error:
                if not is_retryable(error) or attempt == self.retries:
                    raise
                wait = self.wait_seconds * 2**attempt
                logger.warning(
                    f"Notify returned {error.status_code}, retrying in {wait}s"
                )
                self.sleep(wait)
        raise AssertionError("unreachable")

    def notifications(self, reference: str) -> list[dict]:
        """Return every email notification Notify holds for a reference.

        Only notifications sent with the same key type are visible, and Notify
        keeps them for 7 days by default.

        Parameters
        ----------
        reference : str
            Reference given when sending.

        Returns
        -------
        list[dict]
            Notification records across all result pages.
        """
        return list(
            self.api.get_all_notifications_iterator(
                template_type="email", reference=reference
            )
        )

    def sent_addresses(self, reference: str) -> set[str]:
        """Return the addresses that already have an email with this reference.

        Parameters
        ----------
        reference : str
            Reference given when sending.

        Returns
        -------
        set[str]
            Normalised addresses.
        """
        return {
            normalise(item["email_address"]) for item in self.notifications(reference)
        }

    def status_counts(self, reference: str) -> Counter[str]:
        """Count notifications for a reference by delivery status.

        Parameters
        ----------
        reference : str
            Reference given when sending.

        Returns
        -------
        Counter[str]
            Number of notifications per status.
        """
        return Counter(item["status"] for item in self.notifications(reference))
