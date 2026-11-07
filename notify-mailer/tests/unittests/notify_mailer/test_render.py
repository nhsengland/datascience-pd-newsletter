from pathlib import Path

import pytest

from notify_mailer.render import (
    Message,
    MessageError,
    clean_value,
    find_problems,
    load_message,
    personalise,
    split_front_matter,
    to_html_page,
    to_standard_markdown,
)


def write_message(tmp_path: Path, front_matter: str, body: str) -> Path:
    path = tmp_path / "m.md"
    path.write_text(f"---\n{front_matter}\n---\n{body}\n", encoding="utf-8")
    return path


class TestSplitFrontMatter:
    def test_splits_values_and_content(self) -> None:
        assert split_front_matter("---\na: 1\nb: {c: x}\n---\nbody\n") == (
            {"a": 1, "b": {"c": "x"}},
            "body\n",
        )

    def test_returns_all_text_without_front_matter(self) -> None:
        assert split_front_matter("just body") == ({}, "just body")


class TestFindProblems:
    @pytest.mark.parametrize(
        "text",
        [
            pytest.param(
                "# Heading\n\n* bullet\n  * nested", id="headings-and-bullets"
            ),
            pytest.param("[link](https://x.org/2026_10/a?b=&c=)", id="link-underscore"),
            pytest.param("^ inset\n\n---", id="inset-and-rule"),
            pytest.param("Bias & Fairness - It's 2 * 3", id="symbols"),
        ],
    )
    def test_accepts_supported_markdown(self, text: str) -> None:
        assert find_problems(text) == []

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("![b](x.png)", "an image (Notify removes images)", id="image"),
            pytest.param(
                "**bold**", "bold text (Notify does not support it)", id="bold"
            ),
            pytest.param(
                "an _italic_ word",
                "italic text (Notify does not support it)",
                id="italic",
            ),
            pytest.param(
                "Hi ((name))",
                "a ((placeholder)) (readers would see it as text)",
                id="placeholder",
            ),
        ],
    )
    def test_flags_unsupported_markdown(self, text: str, expected: str) -> None:
        assert find_problems(text) == [expected]


class TestLoadMessage:
    def test_renders_without_layout(self, tmp_path: Path) -> None:
        path = tmp_path / "note.md"
        path.write_text("---\nsubject: Hello\n---\nBody text\n", encoding="utf-8")
        assert load_message(path) == Message("Hello", "Body text", "note")

    def test_applies_layout_fields(self, tmp_path: Path) -> None:
        (tmp_path / "_layout.md").write_text(
            "---\nsubject: News - ${month}\nreference: news-${stem}\n---\n"
            "# ${month}\n\n${content}\n",
            encoding="utf-8",
        )
        path = tmp_path / "2026_11.md"
        path.write_text(
            "---\nlayout: _layout.md\nmonth: November 2026\n---\n* item\n",
            encoding="utf-8",
        )
        assert load_message(path) == Message(
            "News - November 2026", "# November 2026\n\n* item", "news-2026_11"
        )

    def test_message_subject_overrides_layout(self, tmp_path: Path) -> None:
        (tmp_path / "_layout.md").write_text(
            "---\nsubject: Layout subject\n---\n${content}\n", encoding="utf-8"
        )
        path = tmp_path / "m.md"
        path.write_text(
            "---\nlayout: _layout.md\nsubject: Own subject\n---\ntext\n",
            encoding="utf-8",
        )
        assert load_message(path).subject == "Own subject"

    def test_rejects_missing_subject(self, tmp_path: Path) -> None:
        path = tmp_path / "m.md"
        path.write_text("text", encoding="utf-8")
        with pytest.raises(MessageError, match="m.md has no subject"):
            load_message(path)

    def test_rejects_missing_layout_value(self, tmp_path: Path) -> None:
        (tmp_path / "_layout.md").write_text(
            "---\nsubject: S\n---\n${month}\n", encoding="utf-8"
        )
        path = tmp_path / "m.md"
        path.write_text("---\nlayout: _layout.md\n---\ntext\n", encoding="utf-8")
        with pytest.raises(MessageError, match="_layout.md needs a value for 'month'"):
            load_message(path)

    def test_rejects_unsupported_formatting(self, tmp_path: Path) -> None:
        path = tmp_path / "m.md"
        path.write_text("---\nsubject: S\n---\n**Big news**\n", encoding="utf-8")
        with pytest.raises(MessageError, match="bold text"):
            load_message(path)

    def test_keeps_recipient_fields_unfilled(self, tmp_path: Path) -> None:
        path = write_message(
            tmp_path,
            "subject: For ${name}\nrecipient_fields:\n  name: colleague",
            "Hi ${name}",
        )
        assert load_message(path) == Message(
            "For ${name}", "Hi ${name}", "m", {"name": "colleague"}
        )

    def test_fills_recipient_fields_from_layout(self, tmp_path: Path) -> None:
        (tmp_path / "_layout.md").write_text(
            "---\nsubject: S\nrecipient_fields:\n  name: colleague\n---\n"
            "Hi ${name}\n\n${content}\n",
            encoding="utf-8",
        )
        path = write_message(tmp_path, "layout: _layout.md", "News")
        assert load_message(path).body == "Hi ${name}\n\nNews"

    def test_rejects_undeclared_field_in_content(self, tmp_path: Path) -> None:
        path = write_message(tmp_path, "subject: S", "Hi ${name}")
        with pytest.raises(MessageError, match="an unfilled"):
            load_message(path)

    def test_rejects_recipient_field_in_reference(self, tmp_path: Path) -> None:
        path = write_message(
            tmp_path,
            "subject: S\nreference: r-${name}\nrecipient_fields:\n  name: x",
            "Hi",
        )
        with pytest.raises(MessageError, match="reference must not use"):
            load_message(path)

    def test_rejects_unsupported_default(self, tmp_path: Path) -> None:
        path = write_message(
            tmp_path, "subject: S\nrecipient_fields:\n  name: '**you**'", "Hi ${name}"
        )
        with pytest.raises(MessageError, match="bold text"):
            load_message(path)


class TestCleanValue:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("Mary-Jane O'Neil", "Mary-Jane O'Neil", id="plain-name"),
            pytest.param("  Sam\n Lee ", "Sam Lee", id="whitespace"),
            pytest.param("[click](https://x.org)", "clickx.org", id="markdown-link"),
            pytest.param("Sam https://x.org", "Sam x.org", id="bare-url"),
            pytest.param("see www.x.org", "see x.org", id="www"),
            pytest.param("HTTP://X.ORG", "X.ORG", id="upper-case-scheme"),
            pytest.param("# Big **bold**", "Big bold", id="heading-and-bold"),
            pytest.param("((field)) ${other}", "field other", id="placeholders"),
        ],
    )
    def test_removes_formatting(self, raw: str, expected: str) -> None:
        assert clean_value(raw) == expected


class TestPersonalise:
    MESSAGE = Message(
        "News for ${name}",
        "Hi ${name} from ${org}",
        "ref",
        {"name": "you", "org": "NHS"},
    )

    @pytest.mark.parametrize(
        ("recipient", "expected_body"),
        [
            pytest.param(
                {"name": "Sam", "org": "Leeds"}, "Hi Sam from Leeds", id="all"
            ),
            pytest.param({"name": "Sam"}, "Hi Sam from NHS", id="missing-column"),
            pytest.param({"name": "  ", "org": ""}, "Hi you from NHS", id="blank"),
            pytest.param({"name": "[x](y)"}, "Hi xy from NHS", id="cleaned"),
        ],
    )
    def test_fills_body(self, recipient: dict[str, str], expected_body: str) -> None:
        assert personalise(self.MESSAGE, recipient).body == expected_body

    def test_fills_subject_and_clears_fields(self) -> None:
        email = personalise(self.MESSAGE, {"name": "Sam"})
        assert (email.subject, email.recipient_fields) == ("News for Sam", {})

    def test_leaves_message_without_fields_unchanged(self) -> None:
        message = Message("S", "Costs $5 and ${x}", "ref")
        assert personalise(message, {"x": "y"}) == message


class TestToStandardMarkdown:
    @pytest.mark.parametrize(
        ("notify", "expected"),
        [
            pytest.param("* a\n  * b", "* a\n    * b", id="nested-bullet"),
            pytest.param("1. a\n  2. b", "1. a\n    2. b", id="nested-number"),
            pytest.param("^ inset", "> inset", id="inset"),
            pytest.param("  text", "  text", id="indented-paragraph"),
            pytest.param("a ^ b", "a ^ b", id="caret-mid-line"),
        ],
    )
    def test_converts_notify_syntax(self, notify: str, expected: str) -> None:
        assert to_standard_markdown(notify) == expected


class TestToHtmlPage:
    def test_sets_title_without_extra_heading(self) -> None:
        page = to_html_page(Message("A & B", "text", "ref"))
        assert "<title>A &amp; B</title>" in page
        assert "<h1>" not in page

    def test_renders_nested_list(self) -> None:
        page = to_html_page(Message("S", "* one\n  * two", "ref"))
        assert "<ul>\n<li>one<ul>\n<li>two</li>\n</ul>\n</li>\n</ul>" in page
