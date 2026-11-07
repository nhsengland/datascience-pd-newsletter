"""Template checks and a file send against the real Notify API, test key only.

Test keys never deliver email. Run with:

    uv run --env-file ../.env pytest -m integration
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest

from notify_mailer.client import NotifyClient
from notify_mailer.files import prepare_file
from notify_mailer.render import Message
from notify_mailer.templates import TEMPLATES, TemplateSpec, template_problems

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> NotifyClient:
    names = ("NOTIFY_API_KEY_TEST", "NOTIFY_TEMPLATE_ID", "NOTIFY_FILE_TEMPLATE_ID")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip(f"Needs {', '.join(missing)}")
    return NotifyClient(
        os.environ["NOTIFY_API_KEY_TEST"],
        os.environ["NOTIFY_TEMPLATE_ID"],
        os.environ["NOTIFY_FILE_TEMPLATE_ID"],
    )


class TestTemplatesInNotify:
    @pytest.mark.parametrize(
        "spec", [pytest.param(s, id=s.variable) for s in TEMPLATES]
    )
    def test_template_is_set_up(self, client: NotifyClient, spec: TemplateSpec) -> None:
        template = client.template(os.environ[spec.variable])
        assert template_problems(spec, template) == []


class TestFileSend:
    def test_file_email_is_accepted(self, client: NotifyClient, tmp_path: Path) -> None:
        report = tmp_path / "synthetic-report.csv"
        report.write_text("region,count\nNorth,1\nSouth,2\n", encoding="utf-8")
        message = Message(
            "Integration file check",
            "# File check\n\nSent with the test key. Not delivered.",
            f"integration-file-{uuid4().hex[:8]}",
        )
        client.send("file-check@example.com", message, prepare_file(report))
        assert sum(client.status_counts(message.reference).values()) == 1
