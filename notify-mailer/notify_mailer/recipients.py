"""Read, clean and update recipient lists stored as CSV files."""

import csv
import re
from pathlib import Path

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RecipientError(ValueError):
    """Raised when a recipient file cannot be used."""


def normalise(address: str) -> str:
    """Return an address with surrounding spaces removed and in lower case.

    Parameters
    ----------
    address : str
        Raw email address.

    Returns
    -------
    str
        Normalised address.
    """
    return address.strip().lower()


def read_recipients(path: Path, column: str = "email") -> dict[str, dict[str, str]]:
    """Read unique, valid recipients and all their columns from a CSV file.

    Rows with a blank address are skipped. Duplicates are dropped, keeping the
    first row.

    Parameters
    ----------
    path : Path
        CSV file with a header row.
    column : str
        Header of the column that holds the addresses.

    Returns
    -------
    dict[str, dict[str, str]]
        Each normalised address, in file order, mapped to its row with values
        stripped of surrounding spaces.

    Raises
    ------
    RecipientError
        If the column is missing or any row holds an invalid address. Errors
        name row numbers, never addresses.
    """
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if column not in (reader.fieldnames or []):
            raise RecipientError(
                f"{path.name} has no '{column}' column. "
                f"Columns found: {reader.fieldnames}"
            )
        rows = [
            (
                number,
                normalise(row[column] or ""),
                {key: (value or "").strip() for key, value in row.items() if key},
            )
            for number, row in enumerate(reader, start=2)
        ]

    invalid = [
        number
        for number, address, _ in rows
        if address and not EMAIL_PATTERN.match(address)
    ]
    if invalid:
        raise RecipientError(f"{path.name} has invalid addresses on rows {invalid}")

    recipients: dict[str, dict[str, str]] = {}
    for _, address, row in rows:
        if address:
            recipients.setdefault(address, row)
    return recipients


def read_addresses(path: Path, column: str = "email") -> list[str]:
    """Read unique, valid addresses from one column of a CSV file.

    Parameters
    ----------
    path : Path
        CSV file with a header row.
    column : str
        Header of the column that holds the addresses.

    Returns
    -------
    list[str]
        Normalised addresses in file order.
    """
    return list(read_recipients(path, column))


def write_addresses(path: Path, addresses: list[str], column: str = "email") -> None:
    """Write addresses to a one-column CSV file.

    Parameters
    ----------
    path : Path
        CSV file to create or replace.
    addresses : list[str]
        Addresses to write.
    column : str
        Header for the address column.
    """
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([column])
        writer.writerows([address] for address in addresses)


def split_unsubscribed(
    recipients: list[str], unsubscribed: list[str]
) -> tuple[list[str], list[str]]:
    """Split recipients into those to keep and those who unsubscribed.

    Parameters
    ----------
    recipients : list[str]
        Current recipient addresses.
    unsubscribed : list[str]
        Addresses that asked to unsubscribe.

    Returns
    -------
    tuple[list[str], list[str]]
        Addresses to keep, then addresses to remove, both in recipient order.
    """
    leaving = set(unsubscribed)
    keep = [address for address in recipients if address not in leaving]
    remove = [address for address in recipients if address in leaving]
    return keep, remove
