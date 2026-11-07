from pathlib import Path

import pytest

from notify_mailer.render import (
    Message,
    MessageError,
    find_problems,
    load_message,
    split_front_matter,
    to_html_page,
    to_standard_markdown,
)

REPO_ROOT = Path(__file__).parents[3]


class TestSplitFrontMatter:
    def test_splits_values_and_content(self) -> None:
        assert split_front_matter("---\na: 1\nb: x\n---\nbody\n") == (
            {"a": "1", "b": "x"},
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

    def test_renders_october_edition(self) -> None:
        message = load_message(REPO_ROOT / "emails" / "2026_10.md")
        assert (message.subject, message.reference) == (
            "Data Science Professional Development Newsletter - October 2026",
            "newsletter-2026_10",
        )


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
