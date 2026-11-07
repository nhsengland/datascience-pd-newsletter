"""Step-by-step set-up of a .env file: API keys and Notify template IDs."""

import os
from collections.abc import Callable
from pathlib import Path

from notifications_python_client.errors import HTTPError

from notify_mailer.client import NotifyClient
from notify_mailer.templates import TEMPLATES, TemplateSpec, template_problems

ENV_LAYOUT = """\
# Template IDS
NOTIFY_TEMPLATE_ID=
NOTIFY_FILE_TEMPLATE_ID=

# API Keys
NOTIFY_API_KEY_TEST=
NOTIFY_API_KEY_TEAM=
NOTIFY_API_KEY_LIVE=
"""

KEYS = (
    ("NOTIFY_API_KEY_TEST", "test", "delivers nothing; use it to try things out"),
    ("NOTIFY_API_KEY_TEAM", "team and guest list", "sends only to your Notify team"),
    ("NOTIFY_API_KEY_LIVE", "live", "sends to anyone; leave blank until you need it"),
)

Ask = Callable[[str], str]
ClientFactory = Callable[[str], NotifyClient]


def read_env_values(path: Path) -> dict[str, str]:
    """Read ``KEY=VALUE`` lines from an env file.

    Parameters
    ----------
    path : Path
        Env file.

    Returns
    -------
    dict[str, str]
        Values by key, with surrounding quotes removed. Blank values are kept.
    """
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def set_env_value(path: Path, key: str, value: str) -> None:
    """Set one value in an env file, keeping its layout and comments.

    Parameters
    ----------
    path : Path
        Env file.
    key : str
        Variable name. Added at the end if the file does not have it.
    value : str
        New value.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key and "=" in line:
            lines[index] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_env_file(path: Path) -> bool:
    """Create an env file from the standard layout, readable only by its owner.

    Parameters
    ----------
    path : Path
        Env file to create.

    Returns
    -------
    bool
        True if the file was created, False if it already existed.
    """
    if path.exists():
        return False
    path.write_text(ENV_LAYOUT, encoding="utf-8")
    os.chmod(path, 0o600)
    return True


def key_works(make_client: ClientFactory, key: str) -> bool:
    """Return whether Notify accepts an API key.

    Parameters
    ----------
    make_client : ClientFactory
        Builds a client from an API key.
    key : str
        API key to check.

    Returns
    -------
    bool
        True if Notify answered a request made with the key. False if Notify
        refused it, or it is too short to be a key (the Notify client raises
        AssertionError for that).
    """
    try:
        make_client(key).email_templates()
    except (AssertionError, HTTPError):
        return False
    return True


def matching_templates(spec: TemplateSpec, templates: list[dict]) -> list[dict]:
    """Return the templates set up exactly as a spec needs.

    Parameters
    ----------
    spec : TemplateSpec
        Expected set-up.
    templates : list[dict]
        Email templates from Notify.

    Returns
    -------
    list[dict]
        Templates with no problems against the spec.
    """
    return [t for t in templates if not template_problems(spec, t)]


def print_instructions(spec: TemplateSpec) -> None:
    """Print exactly how to create a template in the Notify portal.

    Parameters
    ----------
    spec : TemplateSpec
        Template to create.
    """
    message = spec.body.replace("\n", "\n             ")
    print(
        f"\nCreate this template in Notify: Templates > New template > Email\n"
        f"  Name:      {spec.name}\n"
        f"  Subject:   {spec.subject}\n"
        f"  Message:   {message}\n"
        "  Tick 'Add an unsubscribe link' if these are subscription emails, "
        "such as a newsletter."
    )


def choose_template(spec: TemplateSpec, matches: list[dict], ask: Ask) -> str:
    """Pick one template ID when more than one template matches.

    Parameters
    ----------
    spec : TemplateSpec
        Template being set up.
    matches : list[dict]
        Matching templates.
    ask : Ask
        Function that asks the user a question.

    Returns
    -------
    str
        Chosen template ID, or an empty string if none was chosen.
    """
    print(f"\nMore than one template matches '{spec.name}':")
    for number, template in enumerate(matches, start=1):
        print(f"  {number}. {template.get('name')} ({template['id']})")
    answer = ask("Which one? Type its number: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(matches):
        return matches[int(answer) - 1]["id"]
    return ""


def set_up_keys(path: Path, ask_secret: Ask, make_client: ClientFactory) -> str:
    """Ask for each missing API key, check it, and save it.

    Parameters
    ----------
    path : Path
        Env file.
    ask_secret : Ask
        Function that asks for a value without showing it.
    make_client : ClientFactory
        Builds a client from an API key.

    Returns
    -------
    str
        A working key to use for the rest of set-up, or an empty string.
    """
    print("\nStep 1 of 2: API keys (Notify: API integration > Create an API key)")
    working = ""
    for variable, kind, purpose in KEYS:
        key = read_env_values(path).get(variable, "")
        while True:
            if key and key_works(make_client, key):
                print(f"OK       {kind} key ({variable})")
                set_env_value(path, variable, key)
                working = working or key
                break
            if key:
                print(f"Notify did not accept that {kind} key.")
            key = ask_secret(
                f"Paste the {kind} key ({purpose}), or press Enter to skip: "
            )
            key = key.strip()
            if not key:
                print(f"Skipped  {kind} key ({variable})")
                break
    return working


def set_up_templates(path: Path, client: NotifyClient, ask: Ask) -> bool:
    """Find each template in Notify by its content and save its ID.

    Parameters
    ----------
    path : Path
        Env file.
    client : NotifyClient
        Client with a working key.
    ask : Ask
        Function that asks the user a question.

    Returns
    -------
    bool
        True if every template is set up.
    """
    print("\nStep 2 of 2: templates")
    all_found = True
    for spec in TEMPLATES:
        while True:
            matches = matching_templates(spec, client.email_templates())
            current = read_env_values(path).get(spec.variable, "")
            if current in {t["id"] for t in matches}:
                chosen = current
            elif len(matches) == 1:
                chosen = matches[0]["id"]
            elif matches:
                chosen = choose_template(spec, matches, ask)
            else:
                print_instructions(spec)
                answer = ask("Press Enter once it is saved, or type 'skip': ")
                if answer.strip().lower() == "skip":
                    print(f"Skipped  {spec.name} ({spec.variable})")
                    all_found = False
                    break
                continue
            if chosen:
                set_env_value(path, spec.variable, chosen)
                print(f"OK       {spec.name} ({spec.variable})")
                break
    return all_found


def run_setup(
    path: Path, ask: Ask, ask_secret: Ask, make_client: ClientFactory
) -> bool:
    """Create or complete an env file with checked keys and template IDs.

    Parameters
    ----------
    path : Path
        Env file.
    ask : Ask
        Function that asks the user a question.
    ask_secret : Ask
        Function that asks for a value without showing it.
    make_client : ClientFactory
        Builds a client from an API key.

    Returns
    -------
    bool
        True if at least one key works and every template is set up.
    """
    if create_env_file(path):
        print(f"Created {path}. It holds secrets, so never commit it.")
    key = set_up_keys(path, ask_secret, make_client)
    if not key:
        print(
            "\nNo working API key, so templates cannot be checked. Add one, run again."
        )
        return False
    done = set_up_templates(path, make_client(key), ask)
    print(f"\nSaved to {path}." if done else f"\nSaved what was set up to {path}.")
    print(
        "Notify's API cannot show the unsubscribe setting. For newsletters, check "
        "'Add an unsubscribe link' is ticked on each template."
    )
    return done
