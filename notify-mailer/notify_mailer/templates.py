"""The Notify templates notify-mailer needs, and checks that they are set up right."""

import re
from dataclasses import dataclass

PLACEHOLDER = re.compile(r"\(\(([^()]+)\)\)")
FILE_PLACEHOLDER = "link_to_file"


@dataclass(frozen=True)
class TemplateSpec:
    """How one Notify template must be set up.

    Attributes
    ----------
    name : str
        Suggested template name in Notify.
    variable : str
        Environment variable that holds the template's ID.
    subject : str
        Exact subject line.
    body : str
        Exact message.
    """

    name: str
    variable: str
    subject: str
    body: str


EMAIL = TemplateSpec(
    name="notify-mailer email",
    variable="NOTIFY_TEMPLATE_ID",
    subject="((subject))",
    body="((body))",
)
EMAIL_WITH_FILE = TemplateSpec(
    name="notify-mailer email with file",
    variable="NOTIFY_FILE_TEMPLATE_ID",
    subject="((subject))",
    body=f"((body))\n\n(({FILE_PLACEHOLDER}))",
)
TEMPLATES = (EMAIL, EMAIL_WITH_FILE)


def placeholders(text: str) -> set[str]:
    """Return the names of the ``((placeholders))`` in some text.

    Parameters
    ----------
    text : str
        Template subject or message.

    Returns
    -------
    set[str]
        Placeholder names, without brackets or surrounding spaces.
    """
    return {name.strip() for name in PLACEHOLDER.findall(text)}


def template_problems(spec: TemplateSpec, template: dict) -> list[str]:
    """Compare a template from the Notify API with how it should be set up.

    Parameters
    ----------
    spec : TemplateSpec
        Expected set-up.
    template : dict
        Template as returned by Notify's get template call.

    Returns
    -------
    list[str]
        One description per problem. Empty if the template is right.
    """
    problems = []
    if template.get("type") != "email":
        problems.append("it is not an email template")
    if (template.get("subject") or "").strip() != spec.subject:
        problems.append(f"the subject must be exactly {spec.subject}")
    if placeholders(template.get("body") or "") != placeholders(spec.body):
        problems.append("the message must contain only: " + " ".join(spec.body.split()))
    return problems
