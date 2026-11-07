from collections import Counter
from pathlib import Path

import pytest
from pytest_mock import MockerFixture, MockType

from notify_mailer import cli
from notify_mailer.campaign import Result
from notify_mailer.recipients import read_addresses


@pytest.fixture
def message_file(tmp_path: Path) -> Path:
    path = tmp_path / "m.md"
    path.write_text("---\nsubject: Hello\n---\nBody\n", encoding="utf-8")
    return path


@pytest.fixture
def recipients_file(tmp_path: Path) -> Path:
    path = tmp_path / "recipients.csv"
    path.write_text("email\na@example.com\nb@example.com\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_client(mocker: MockerFixture) -> MockType:
    client = mocker.MagicMock()
    client.sent_addresses.return_value = {"a@example.com"}
    mocker.patch.object(cli, "make_client", return_value=client)
    return client


@pytest.fixture
def no_env(tmp_path: Path) -> list[str]:
    return ["--env-file", str(tmp_path / "missing.env")]


class TestLoadEnvFile:
    def test_sets_missing_variables_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KEEP_ME", "outer")
        monkeypatch.delenv("NEW_ONE", raising=False)
        path = tmp_path / ".env"
        path.write_text("# comment\nKEEP_ME=inner\nNEW_ONE='value'\n", encoding="utf-8")
        cli.load_env_file(path)
        assert (cli.os.environ["KEEP_ME"], cli.os.environ["NEW_ONE"]) == (
            "outer",
            "value",
        )


class TestRequiredVariable:
    def test_exits_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NOTIFY_MISSING", raising=False)
        with pytest.raises(SystemExit, match="NOTIFY_MISSING is not set"):
            cli.required_variable("NOTIFY_MISSING")


class TestPreview:
    def test_prints_rendered_message(
        self, message_file: Path, no_env: list[str], capsys: pytest.CaptureFixture
    ) -> None:
        cli.main([*no_env, "preview", str(message_file)])
        assert capsys.readouterr().out == "Subject:   Hello\nReference: m\n\nBody\n"

    def test_fills_fields_from_chosen_row(
        self, tmp_path: Path, no_env: list[str], capsys: pytest.CaptureFixture
    ) -> None:
        message = tmp_path / "p.md"
        message.write_text(
            "---\nsubject: Hello\nrecipient_fields:\n  name: you\n---\nHi ${name}\n",
            encoding="utf-8",
        )
        people = tmp_path / "people.csv"
        people.write_text(
            "email,name\na@example.com,Sam\nb@example.com,Ali\n", encoding="utf-8"
        )
        cli.main(
            [
                *no_env,
                "preview",
                str(message),
                "--recipients",
                str(people),
                "--row",
                "2",
            ]
        )
        assert capsys.readouterr().out == (
            "Subject:   Hello\nReference: p\n"
            "Recipient fields: name (default 'you')\n\nHi Ali\n"
        )

    def test_rejects_row_outside_list(
        self, message_file: Path, recipients_file: Path, no_env: list[str]
    ) -> None:
        with pytest.raises(SystemExit, match="--row must be between 1 and 2"):
            cli.main(
                [
                    *no_env,
                    "preview",
                    str(message_file),
                    "--recipients",
                    str(recipients_file),
                    "--row",
                    "3",
                ]
            )


class TestSend:
    def test_dry_run_only_counts(
        self,
        message_file: Path,
        recipients_file: Path,
        fake_client: MockType,
        no_env: list[str],
        capsys: pytest.CaptureFixture,
    ) -> None:
        cli.main(
            [
                *no_env,
                "send",
                str(message_file),
                "--recipients",
                str(recipients_file),
                "--dry-run",
            ]
        )
        assert capsys.readouterr().out == (
            "Key: test | Reference: m | Recipients: 2 | "
            "Already sent: 1 | To send now: 1\n"
        )
        fake_client.send.assert_not_called()

    def test_sends_only_to_new_addresses(
        self,
        message_file: Path,
        recipients_file: Path,
        fake_client: MockType,
        no_env: list[str],
    ) -> None:
        cli.main(
            [*no_env, "send", str(message_file), "--recipients", str(recipients_file)]
        )
        assert [call.args[0] for call in fake_client.send.call_args_list] == [
            "b@example.com"
        ]

    @pytest.mark.parametrize(
        ("answer", "sends"),
        [pytest.param("1", 1, id="confirmed"), pytest.param("2", 0, id="wrong-count")],
    )
    def test_live_needs_typed_count(
        self,
        message_file: Path,
        recipients_file: Path,
        fake_client: MockType,
        no_env: list[str],
        monkeypatch: pytest.MonkeyPatch,
        answer: str,
        sends: int,
    ) -> None:
        monkeypatch.setattr("builtins.input", lambda _: answer)
        args = [
            *no_env,
            "send",
            str(message_file),
            "--recipients",
            str(recipients_file),
            "--key",
            "live",
        ]
        if sends:
            cli.main(args)
        else:
            with pytest.raises(SystemExit, match="Not sent."):
                cli.main(args)
        assert fake_client.send.call_count == sends

    def test_writes_failed_addresses(
        self,
        message_file: Path,
        recipients_file: Path,
        fake_client: MockType,
        no_env: list[str],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(cli, "send_all", return_value=Result(0, ["b@example.com"]))
        with pytest.raises(SystemExit, match="1 addresses failed"):
            cli.main(
                [
                    *no_env,
                    "send",
                    str(message_file),
                    "--recipients",
                    str(recipients_file),
                ]
            )
        failed = recipients_file.parent / "failed-m.csv"
        assert read_addresses(failed) == ["b@example.com"]


class TestStatus:
    def test_prints_counts(
        self, fake_client: MockType, no_env: list[str], capsys: pytest.CaptureFixture
    ) -> None:
        fake_client.status_counts.return_value = Counter(delivered=2, sending=1)
        cli.main([*no_env, "status", "ref-1"])
        assert capsys.readouterr().out == "delivered: 2\nsending: 1\ntotal: 3\n"


class TestUnsubscribe:
    def test_removes_after_confirmation(
        self,
        tmp_path: Path,
        recipients_file: Path,
        no_env: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        report = tmp_path / "report.csv"
        report.write_text("email_address\nA@example.com\n", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        cli.main(
            [*no_env, "unsubscribe", str(report), "--recipients", str(recipients_file)]
        )
        assert read_addresses(recipients_file) == ["b@example.com"]

    def test_keeps_list_when_not_confirmed(
        self,
        tmp_path: Path,
        recipients_file: Path,
        no_env: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        report = tmp_path / "report.csv"
        report.write_text("email_address\na@example.com\n", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "no")
        with pytest.raises(SystemExit, match="Nothing removed."):
            cli.main(
                [
                    *no_env,
                    "unsubscribe",
                    str(report),
                    "--recipients",
                    str(recipients_file),
                ]
            )
        assert read_addresses(recipients_file) == ["a@example.com", "b@example.com"]


class TestTeams:
    def test_writes_html_page(
        self, message_file: Path, tmp_path: Path, no_env: list[str]
    ) -> None:
        output = tmp_path / "out.html"
        cli.main([*no_env, "teams", str(message_file), "--output", str(output)])
        assert "<p>Body</p>" in output.read_text(encoding="utf-8")
