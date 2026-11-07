"""Work out who still needs an email, then send it to them."""

from dataclasses import dataclass, field

from loguru import logger
from notifications_python_client.errors import HTTPError

from notify_mailer.client import NotifyClient
from notify_mailer.render import Message, personalise


@dataclass(frozen=True)
class Plan:
    """Who a send will reach.

    Attributes
    ----------
    to_send : list[str]
        Addresses that do not have this email yet.
    already_sent : int
        Recipients skipped because they already have it.
    """

    to_send: list[str]
    already_sent: int


@dataclass
class Result:
    """Outcome of a send.

    Attributes
    ----------
    sent : int
        Emails Notify accepted.
    failed : list[str]
        Addresses Notify rejected.
    """

    sent: int = 0
    failed: list[str] = field(default_factory=list)


def plan_send(client: NotifyClient, message: Message, recipients: list[str]) -> Plan:
    """Skip recipients who already have an email with this message's reference.

    Parameters
    ----------
    client : NotifyClient
        Client using the key the send will use.
    message : Message
        Rendered message.
    recipients : list[str]
        Normalised, unique addresses.

    Returns
    -------
    Plan
        Addresses still to send to, and how many were skipped.
    """
    done = client.sent_addresses(message.reference)
    to_send = [address for address in recipients if address not in done]
    return Plan(to_send=to_send, already_sent=len(recipients) - len(to_send))


def send_all(
    client: NotifyClient,
    message: Message,
    addresses: list[str],
    recipients: dict[str, dict[str, str]] | None = None,
    file: dict | None = None,
    progress_every: int = 50,
) -> Result:
    """Send the message to each address, carrying on past rejected addresses.

    Parameters
    ----------
    client : NotifyClient
        Client to send with.
    message : Message
        Message from ``load_message``. Its recipient fields are filled for
        each address from ``recipients``.
    addresses : list[str]
        Addresses to send to.
    recipients : dict[str, dict[str, str]] | None
        Recipient rows by address. Addresses without a row get the defaults.
    file : dict | None
        File from ``prepare_file``, prepared once and linked from every email.
    progress_every : int
        Log progress after this many attempts.

    Returns
    -------
    Result
        Count sent and addresses rejected. Logs never contain addresses.
    """
    rows = recipients or {}
    result = Result()
    for number, address in enumerate(addresses, start=1):
        try:
            client.send(address, personalise(message, rows.get(address, {})), file)
            result.sent += 1
        except HTTPError as error:
            result.failed.append(address)
            logger.error(f"Recipient {number} rejected by Notify ({error.status_code})")
        if number % progress_every == 0:
            logger.info(f"Progress: {number}/{len(addresses)}")
    logger.info(f"Finished: {result.sent} sent, {len(result.failed)} failed")
    return result
