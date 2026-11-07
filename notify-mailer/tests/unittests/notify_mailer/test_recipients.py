from pathlib import Path

import pytest

from notify_mailer.recipients import (
    RecipientError,
    normalise,
    read_addresses,
    split_unsubscribed,
    write_addresses,
)


def write_csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestNormalise:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("a@example.com", "a@example.com", id="already-clean"),
            pytest.param("  A@Example.COM ", "a@example.com", id="spaces-and-case"),
        ],
    )
    def test_returns_clean_address(self, raw: str, expected: str) -> None:
        assert normalise(raw) == expected


class TestReadAddresses:
    def test_reads_addresses_in_order(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "email\nb@example.com\na@example.com\n")
        assert read_addresses(path) == ["b@example.com", "a@example.com"]

    def test_drops_duplicates_after_normalising(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "email\na@example.com\n A@EXAMPLE.com\n")
        assert read_addresses(path) == ["a@example.com"]

    def test_skips_blank_cells(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "email\na@example.com\n\n  \n")
        assert read_addresses(path) == ["a@example.com"]

    def test_reads_named_column(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "name,email_address\nx,a@example.com\n")
        assert read_addresses(path, column="email_address") == ["a@example.com"]

    def test_handles_excel_byte_order_mark(self, tmp_path: Path) -> None:
        path = tmp_path / "r.csv"
        path.write_text("email\na@example.com\n", encoding="utf-8-sig")
        assert read_addresses(path) == ["a@example.com"]

    def test_rejects_missing_column(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "address\na@example.com\n")
        with pytest.raises(RecipientError, match="no 'email' column"):
            read_addresses(path)

    def test_reports_invalid_rows_without_addresses(self, tmp_path: Path) -> None:
        path = write_csv(tmp_path / "r.csv", "email\na@example.com\nnot-an-email\n")
        with pytest.raises(RecipientError) as error:
            read_addresses(path)
        assert str(error.value) == "r.csv has invalid addresses on rows [3]"


class TestWriteAddresses:
    def test_round_trips_through_read(self, tmp_path: Path) -> None:
        path = tmp_path / "r.csv"
        write_addresses(path, ["a@example.com", "b@example.com"])
        assert read_addresses(path) == ["a@example.com", "b@example.com"]


class TestSplitUnsubscribed:
    def test_splits_keep_and_remove(self) -> None:
        keep, remove = split_unsubscribed(
            ["a@example.com", "b@example.com", "c@example.com"], ["b@example.com"]
        )
        assert (keep, remove) == (["a@example.com", "c@example.com"], ["b@example.com"])

    def test_ignores_unknown_unsubscribes(self) -> None:
        assert split_unsubscribed(["a@example.com"], ["z@example.com"]) == (
            ["a@example.com"],
            [],
        )
