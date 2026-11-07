import base64
from pathlib import Path

import pytest

from notify_mailer.files import FileError, check_file, prepare_file


def write_file(tmp_path: Path, name: str, content: bytes = b"a,b\n1,2\n") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


class TestCheckFile:
    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("report.xlsx", id="excel"),
            pytest.param("data.CSV", id="upper-case-suffix"),
            pytest.param("notes.txt", id="text"),
            pytest.param("summary.pdf", id="pdf"),
        ],
    )
    def test_accepts_supported_files(self, tmp_path: Path, name: str) -> None:
        check_file(write_file(tmp_path, name))

    def test_rejects_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileError, match="No file at"):
            check_file(tmp_path / "missing.csv")

    def test_suggests_txt_for_log_files(self, tmp_path: Path) -> None:
        with pytest.raises(FileError, match="Save as .txt"):
            check_file(write_file(tmp_path, "run.log"))

    def test_rejects_unsupported_type(self, tmp_path: Path) -> None:
        with pytest.raises(FileError, match="Notify only accepts"):
            check_file(write_file(tmp_path, "tool.exe"))

    def test_rejects_files_over_2mb(self, tmp_path: Path) -> None:
        path = write_file(tmp_path, "big.csv", b"x" * (2 * 1024 * 1024 + 1))
        with pytest.raises(FileError, match="Notify's limit is 2MB"):
            check_file(path)

    def test_accepts_exactly_2mb(self, tmp_path: Path) -> None:
        check_file(write_file(tmp_path, "edge.csv", b"x" * (2 * 1024 * 1024)))

    def test_rejects_long_names(self, tmp_path: Path) -> None:
        with pytest.raises(FileError, match="100 characters or fewer"):
            check_file(write_file(tmp_path, "a" * 97 + ".csv"))


class TestPrepareFile:
    def test_encodes_file_with_safe_defaults(self, tmp_path: Path) -> None:
        path = write_file(tmp_path, "report.csv", b"a,b\n")
        assert prepare_file(path) == {
            "file": base64.b64encode(b"a,b\n").decode("ascii"),
            "filename": "report.csv",
            "confirm_email_before_download": True,
            "retention_period": "26 weeks",
        }

    @pytest.mark.parametrize(
        ("weeks", "expected"),
        [pytest.param(1, "1 week", id="one"), pytest.param(78, "78 weeks", id="max")],
    )
    def test_formats_retention(self, tmp_path: Path, weeks: int, expected: str) -> None:
        path = write_file(tmp_path, "r.csv")
        assert prepare_file(path, retention_weeks=weeks)["retention_period"] == expected

    @pytest.mark.parametrize(
        "weeks", [pytest.param(0, id="zero"), pytest.param(79, id="too-long")]
    )
    def test_rejects_retention_out_of_range(self, tmp_path: Path, weeks: int) -> None:
        with pytest.raises(FileError, match="from 1 to 78"):
            prepare_file(write_file(tmp_path, "r.csv"), retention_weeks=weeks)

    def test_can_turn_off_email_check(self, tmp_path: Path) -> None:
        file = prepare_file(write_file(tmp_path, "r.csv"), confirm_email=False)
        assert file["confirm_email_before_download"] is False
