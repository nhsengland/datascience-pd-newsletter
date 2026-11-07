"""Turn Markdown message files into an email subject and body."""

import re
from dataclasses import dataclass, field, replace
from html import escape
from pathlib import Path
from string import Template
from typing import Any

import markdown
import yaml

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
NESTED_LIST_INDENT = re.compile(r"^( +)(?=[*+-] |\d+\. )", re.MULTILINE)
INSET_TEXT = re.compile(r"^\^ ?", re.MULTILINE)
FIELD = re.compile(r"\$\{(\w+)\}")
FORMATTING_CHARACTERS = re.compile(r"[\\`*_{}\[\]()<>#^|~$]")
LINK_STARTS = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://|\bwww\.")

UNSUPPORTED = {
    "an image (Notify removes images)": re.compile(r"!\[[^\]]*\]\([^)]*\)"),
    "bold text (Notify does not support it)": re.compile(r"\*\*|__"),
    "italic text (Notify does not support it)": re.compile(
        r"(?<![\w*])([*_])(?!\s)[^*_\n]+?(?<!\s)\1(?![\w*])"
    ),
    "a ((placeholder)) (readers would see it as text)": re.compile(r"\(\(.*?\)\)"),
    "an unfilled ${field} (add it to recipient_fields or the front matter)": FIELD,
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
    recipient_fields : dict[str, str]
        Fields filled per recipient by ``personalise``, mapped to the value used
        when a recipient has none. Their ``${name}`` markers stay in the subject
        and body until then.
    """

    subject: str
    body: str
    reference: str
    recipient_fields: dict[str, str] = field(default_factory=dict)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split a file into its YAML front matter and the content after it.

    Parameters
    ----------
    text : str
        Full file text.

    Returns
    -------
    tuple[dict[str, Any], str]
        Front matter values, and the remaining content.
    """
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


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
    to ``${stem}``. Values in the message's front matter override the layout's.

    ``recipient_fields`` maps fields filled per recipient (from columns of the
    recipient list) to a default for recipients with no value. They are left
    in place here and filled by ``personalise``.

    Parameters
    ----------
    path : Path
        Message file.

    Returns
    -------
    Message
        Rendered subject, body and reference, with recipient fields unfilled.

    Raises
    ------
    MessageError
        If a value is missing, the reference uses a recipient field, or the
        email would have unsupported formatting for a recipient with no values.
    """
    settings, content = split_front_matter(path.read_text(encoding="utf-8"))
    layout_path, layout_body = path, None
    if "layout" in settings:
        layout_path = path.parent / str(settings["layout"])
        layout_settings, layout_body = split_front_matter(
            layout_path.read_text(encoding="utf-8")
        )
        settings = {**layout_settings, **settings}
    if "subject" not in settings:
        raise MessageError(f"{path.name} has no subject")

    recipient_fields = {
        str(name): str(default)
        for name, default in (settings.pop("recipient_fields", None) or {}).items()
    }
    values = {
        "stem": path.stem,
        **{key: str(value) for key, value in settings.items()},
        "content": content.strip(),
        **{name: f"${{{name}}}" for name in recipient_fields},
    }
    body = fill(layout_body, values, layout_path) if layout_body else content
    message = Message(
        subject=fill(str(settings["subject"]), values, path).strip(),
        body=body.strip(),
        reference=fill(str(settings.get("reference", "${stem}")), values, path).strip(),
        recipient_fields=recipient_fields,
    )
    if FIELD.search(message.reference):
        raise MessageError(f"{path.name} reference must not use recipient fields")

    example = personalise(message, {})
    problems = find_problems(example.subject) + find_problems(example.body)
    if problems:
        raise MessageError(f"{path.name} contains {', '.join(problems)}")
    return message


def clean_value(value: str) -> str:
    """Make a recipient value safe to put into Markdown.

    Characters that could add formatting or placeholders are removed, as are
    URL schemes and ``www.`` (Notify turns bare URLs into links). Line breaks
    become spaces, so a value can only ever appear as plain text.

    Parameters
    ----------
    value : str
        Value from the recipient list.

    Returns
    -------
    str
        Cleaned value.
    """
    value = FORMATTING_CHARACTERS.sub("", LINK_STARTS.sub("", value))
    return " ".join(value.split())


def personalise(message: Message, recipient: dict[str, str]) -> Message:
    """Fill a message's recipient fields for one recipient.

    Parameters
    ----------
    message : Message
        Message from ``load_message``.
    recipient : dict[str, str]
        The recipient's row from the recipient list. Missing or blank values
        use the field's default.

    Returns
    -------
    Message
        Message with every recipient field filled.
    """
    values = {
        name: clean_value(recipient.get(name, "")) or default
        for name, default in message.recipient_fields.items()
    }

    def fill_fields(text: str) -> str:
        return FIELD.sub(lambda match: values.get(match[1], match[0]), text)

    return replace(
        message,
        subject=fill_fields(message.subject),
        body=fill_fields(message.body),
        recipient_fields={},
    )


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
