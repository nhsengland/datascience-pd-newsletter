import pytest

from notify_mailer.templates import (
    EMAIL,
    EMAIL_WITH_FILE,
    TemplateSpec,
    placeholders,
    template_problems,
)


class TestPlaceholders:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("((body))", {"body"}, id="one"),
            pytest.param(
                "((body))\n\n(( link_to_file ))", {"body", "link_to_file"}, id="spaces"
            ),
            pytest.param("no placeholders", set(), id="none"),
        ],
    )
    def test_finds_names(self, text: str, expected: set[str]) -> None:
        assert placeholders(text) == expected


class TestTemplateProblems:
    @pytest.mark.parametrize(
        ("spec", "template"),
        [
            pytest.param(
                EMAIL,
                {"type": "email", "subject": "((subject))", "body": "((body))"},
                id="email",
            ),
            pytest.param(
                EMAIL_WITH_FILE,
                {
                    "type": "email",
                    "subject": " ((subject)) ",
                    "body": "((body))\n((link_to_file))",
                },
                id="file-with-different-spacing",
            ),
        ],
    )
    def test_accepts_correct_templates(
        self, spec: TemplateSpec, template: dict
    ) -> None:
        assert template_problems(spec, template) == []

    def test_reports_each_problem(self) -> None:
        template = {"type": "sms", "subject": "Hello", "body": "((body)) ((name))"}
        assert template_problems(EMAIL, template) == [
            "it is not an email template",
            "the subject must be exactly ((subject))",
            "the message must contain only: ((body))",
        ]

    def test_reports_missing_file_placeholder(self) -> None:
        template = {"type": "email", "subject": "((subject))", "body": "((body))"}
        assert template_problems(EMAIL_WITH_FILE, template) == [
            "the message must contain only: ((body)) ((link_to_file))"
        ]
