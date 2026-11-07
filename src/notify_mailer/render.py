"""Turn Markdown message files into an email subject and body."""

import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template

import markdown
import yaml

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
NESTED_LIST_INDENT = re.compile(r"^( +)(?=[*+-] |\d+\. )", re.MULTILINE)
INSET_TEXT = re.compile(r"^\^ ?", re.MULTILINE)

UNSUPPORTED = {
    "an image (Notify removes images)": re.compile(r"!\[[^\]]*\]\([^)]*\)"),
    "bold text (Notify does not support it)": re.compile(r"\*\*|__"),
    "italic text (Notify does not support it)": re.compile(
        r"(?<![\w*])([*_])(?!\s)[^*_\n]+?(?<!\s)\1(?![\w*])"
    ),
    "a ((placeholder)) (readers would see it as text)": re.compile(r"\(\(.*?\)\)"),
}


class MessageError(ValueError):
    """Raised when a message file cannot be rendered or would render badly."""


@dataclass(frozen=True)
class Message:
    """A rendered email ready to send.

    Attributes
    ----------
    subject : str
        Email subject line.
    body : str
        Email body in Notify Markdown.
    reference : str
        Identifier shared by every email in one send. It must not hold personal data.
    """

    subject: str
    body: str
    reference: str


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a file into its YAML front matter and the content after it.

    Parameters
    ----------
    text : str
        Full file text.

    Returns
    -------
    tuple[dict[str, str], str]
        Front matter values as strings, and the remaining content.
    """
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    values = yaml.safe_load(match.group(1)) or {}
    return {key: str(value) for key, value in values.items()}, match.group(2)


def find_problems(text: str) -> list[str]:
    """List formatting that Notify would drop or show wrongly.

    Parameters
    ----------
    text : str
        Subject or body text.

    Returns
    -------
    list[str]
        One description per kind of problem found.
    """
    return [problem for problem, pattern in UNSUPPORTED.items() if pattern.search(text)]


def fill(template: str, values: dict[str, str], source: Path) -> str:
    """Fill ``${name}`` fields in a template.

    Parameters
    ----------
    template : str
        Text containing ``${name}`` fields.
    values : dict[str, str]
        Values for the fields.
    source : Path
        File the template came from, used in error messages.

    Returns
    -------
    str
        Filled-in text.

    Raises
    ------
    MessageError
        If a field has no value.
    """
    try:
        return Template(template).substitute(values)
    except KeyError as missing:
        raise MessageError(f"{source.name} needs a value for {missing}") from None


def load_message(path: Path) -> Message:
    """Render a message file, applying its layout if it names one.

    A message file is Markdown with optional YAML front matter. If the front
    matter has a ``layout``, that file (relative to the message) wraps the
    content: its ``${content}`` field takes the message content and other
    fields take front matter values. ``${stem}`` is the message file name
    without its extension. ``subject`` is required and ``reference`` defaults
    to ``${stem}``.

    Parameters
    ----------
    path : Path
        Message file.

    Returns
    -------
    Message
        Rendered subject, body and reference.

    Raises
    ------
    MessageError
        If a value is missing or the result has unsupported formatting.
    """
    values, content = split_front_matter(path.read_text(encoding="utf-8"))
    values = {"stem": path.stem, **values, "content": content.strip()}
    fields, body = {}, content

    if "layout" in values:
        layout_path = path.parent / values["layout"]
        fields, layout_body = split_front_matter(
            layout_path.read_text(encoding="utf-8")
        )
        body = fill(layout_body, values, layout_path)

    fields = {
        **fields,
        **{k: v for k, v in values.items() if k in ("subject", "reference")},
    }
    if "subject" not in fields:
        raise MessageError(f"{path.name} has no subject")

    message = Message(
        subject=fill(fields["subject"], values, path).strip(),
        body=body.strip(),
        reference=fill(fields.get("reference", "${stem}"), values, path).strip(),
    )
    problems = find_problems(message.subject) + find_problems(message.body)
    if problems:
        raise MessageError(f"{path.name} contains {', '.join(problems)}")
    return message


def to_standard_markdown(body: str) -> str:
    """Convert Notify Markdown into standard Markdown.

    Notify accepts two-space nested lists and ``^`` for inset text. Standard
    Markdown needs four-space nesting and ``>`` for a quote.

    Parameters
    ----------
    body : str
        Body in Notify Markdown.

    Returns
    -------
    str
        Body in standard Markdown.
    """
    body = NESTED_LIST_INDENT.sub(lambda match: match.group(1) * 2, body)
    return INSET_TEXT.sub("> ", body)


def to_html_page(message: Message) -> str:
    """Render a message as a standalone HTML page for copying into Teams.

    Parameters
    ----------
    message : Message
        Rendered message.

    Returns
    -------
    str
        HTML document.
    """
    body = markdown.markdown(to_standard_markdown(message.body))
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{escape(message.subject)}</title>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )
