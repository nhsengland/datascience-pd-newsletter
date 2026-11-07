import stat
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from notifications_python_client.errors import HTTPError

from notify_mailer.setup_wizard import (
    ENV_LAYOUT,
    create_env_file,
    matching_templates,
    read_env_values,
    run_setup,
    set_env_value,
)
from notify_mailer.templates import EMAIL, EMAIL_WITH_FILE, TemplateSpec

EMAIL_TEMPLATE = {
    "id": "t-email",
    "name": "notify-mailer email",
    "type": "email",
    "subject": "((subject))",
    "body": "((body))",
}
FILE_TEMPLATE = {
    "id": "t-file",
    "name": "notify-mailer email with file",
    "type": "email",
    "subject": "((subject))",
    "body": "((body))\n\n((link_to_file))",
}
OTHER_TEMPLATE = {
    "id": "t-other",
    "name": "Something else",
    "type": "email",
    "subject": "Hello",
    "body": "Hi",
}


class FakeService:
    def __init__(self, templates: list[dict], valid_keys: set[str]) -> None:
        self.templates = templates
        self.valid_keys = valid_keys

    def client(self, key: str) -> "FakeClient":
        if key == "too-short":
            raise AssertionError("Missing service ID")
        return FakeClient(self, key)


class FakeClient:
    def __init__(self, service: FakeService, key: str) -> None:
        self.service = service
        self.key = key

    def email_templates(self) -> list[dict]:
        if self.key not in self.service.valid_keys:
            raise HTTPError(response=None, message="Invalid token")
        return list(self.service.templates)


def answers(*replies: str) -> Callable[[str], str]:
    queue: Iterator[str] = iter(replies)
    return lambda _prompt: next(queue)


@pytest.fixture
def env_path(tmp_path: Path) -> Path:
    return tmp_path / ".env"


class TestReadEnvValues:
    def test_reads_values_and_skips_comments(self, env_path: Path) -> None:
        env_path.write_text("# c\nA=1\nB='two'\nC=\n", encoding="utf-8")
        assert read_env_values(env_path) == {"A": "1", "B": "two", "C": ""}


class TestSetEnvValue:
    def test_replaces_value_in_place(self, env_path: Path) -> None:
        env_path.write_text("# keep\nA=old\nB=2\n", encoding="utf-8")
        set_env_value(env_path, "A", "new")
        assert env_path.read_text(encoding="utf-8") == "# keep\nA=new\nB=2\n"

    def test_appends_missing_key(self, env_path: Path) -> None:
        env_path.write_text("A=1\n", encoding="utf-8")
        set_env_value(env_path, "B", "2")
        assert env_path.read_text(encoding="utf-8") == "A=1\nB=2\n"


class TestCreateEnvFile:
    def test_creates_private_file_from_layout(self, env_path: Path) -> None:
        assert create_env_file(env_path) is True
        assert env_path.read_text(encoding="utf-8") == ENV_LAYOUT
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600

    def test_leaves_existing_file(self, env_path: Path) -> None:
        env_path.write_text("A=1\n", encoding="utf-8")
        assert create_env_file(env_path) is False
        assert env_path.read_text(encoding="utf-8") == "A=1\n"


class TestMatchingTemplates:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            pytest.param(EMAIL, ["t-email"], id="email"),
            pytest.param(EMAIL_WITH_FILE, ["t-file"], id="file"),
        ],
    )
    def test_matches_by_content(self, spec: TemplateSpec, expected: list[str]) -> None:
        templates = [EMAIL_TEMPLATE, FILE_TEMPLATE, OTHER_TEMPLATE]
        assert [t["id"] for t in matching_templates(spec, templates)] == expected


class TestRunSetup:
    def test_new_file_with_templates_found_automatically(
        self, env_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        service = FakeService(
            [EMAIL_TEMPLATE, FILE_TEMPLATE, OTHER_TEMPLATE], {"k-test"}
        )
        done = run_setup(
            env_path,
            ask=answers(),
            ask_secret=answers("k-test", "bad-key", "", ""),
            make_client=service.client,
        )
        assert done is True
        assert read_env_values(env_path) == {
            "NOTIFY_TEMPLATE_ID": "t-email",
            "NOTIFY_FILE_TEMPLATE_ID": "t-file",
            "NOTIFY_API_KEY_TEST": "k-test",
            "NOTIFY_API_KEY_TEAM": "",
            "NOTIFY_API_KEY_LIVE": "",
        }
        output = capsys.readouterr().out
        assert "Notify did not accept that team and guest list key." in output
        assert "k-test" not in output

    def test_keeps_working_keys_already_saved(self, env_path: Path) -> None:
        env_path.write_text(
            ENV_LAYOUT.replace("NOTIFY_API_KEY_TEAM=", "NOTIFY_API_KEY_TEAM=k-team"),
            encoding="utf-8",
        )
        service = FakeService([EMAIL_TEMPLATE, FILE_TEMPLATE], {"k-team"})
        assert run_setup(env_path, answers(), answers("", ""), service.client) is True
        assert read_env_values(env_path)["NOTIFY_API_KEY_TEAM"] == "k-team"

    def test_waits_while_a_template_is_created(
        self, env_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        service = FakeService([EMAIL_TEMPLATE], {"k-test"})

        def create_then_continue(_prompt: str) -> str:
            service.templates.append(FILE_TEMPLATE)
            return ""

        done = run_setup(
            env_path, create_then_continue, answers("k-test", "", ""), service.client
        )
        assert done is True
        assert read_env_values(env_path)["NOTIFY_FILE_TEMPLATE_ID"] == "t-file"
        assert "Name:      notify-mailer email with file" in capsys.readouterr().out

    def test_reports_skipped_template(self, env_path: Path) -> None:
        service = FakeService([EMAIL_TEMPLATE], {"k-test"})
        done = run_setup(
            env_path, answers("skip"), answers("k-test", "", ""), service.client
        )
        assert done is False
        assert read_env_values(env_path)["NOTIFY_FILE_TEMPLATE_ID"] == ""

    def test_asks_which_when_several_match(self, env_path: Path) -> None:
        copy = {**EMAIL_TEMPLATE, "id": "t-email-copy", "name": "copy"}
        service = FakeService([EMAIL_TEMPLATE, copy, FILE_TEMPLATE], {"k-test"})
        run_setup(env_path, answers("2"), answers("k-test", "", ""), service.client)
        assert read_env_values(env_path)["NOTIFY_TEMPLATE_ID"] == "t-email-copy"

    def test_asks_again_after_a_partial_key(self, env_path: Path) -> None:
        service = FakeService([EMAIL_TEMPLATE, FILE_TEMPLATE], {"k-test"})
        secrets = answers("too-short", "k-test", "", "")
        assert run_setup(env_path, answers(), secrets, service.client) is True
        assert read_env_values(env_path)["NOTIFY_API_KEY_TEST"] == "k-test"

    def test_stops_without_a_working_key(self, env_path: Path) -> None:
        service = FakeService([EMAIL_TEMPLATE, FILE_TEMPLATE], set())
        assert (
            run_setup(env_path, answers(), answers("", "", ""), service.client) is False
        )
