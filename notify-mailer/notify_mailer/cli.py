"""Command line for previewing, sending and tracking emails."""

import argparse
import getpass
import os
import sys
from pathlib import Path

from loguru import logger
from notifications_python_client.errors import HTTPError

from notify_mailer.campaign import plan_send, send_all
from notify_mailer.client import NotifyClient
from notify_mailer.files import prepare_file
from notify_mailer.recipients import (
    read_addresses,
    read_recipients,
    split_unsubscribed,
    write_addresses,
)
from notify_mailer.render import load_message, personalise, to_html_page
from notify_mailer.setup_wizard import run_setup
from notify_mailer.templates import EMAIL, EMAIL_WITH_FILE, TEMPLATES, template_problems

KEY_VARIABLES = {
    "test": "NOTIFY_API_KEY_TEST",
    "team": "NOTIFY_API_KEY_TEAM",
    "live": "NOTIFY_API_KEY_LIVE",
}


def load_env_file(path: Path) -> None:
    """Load ``KEY=VALUE`` lines into the environment without overriding it.

    Parameters
    ----------
    path : Path
        Env file. Nothing happens if it does not exist.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def required_variable(name: str) -> str:
    """Return an environment variable or stop with a clear message.

    Parameters
    ----------
    name : str
        Variable name.

    Returns
    -------
    str
        Variable value.
    """
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"{name} is not set. Add it to .env or the environment.")
    return value


def make_client(key_type: str, with_file: bool = False) -> NotifyClient:
    """Build a client for the chosen key type.

    Parameters
    ----------
    key_type : str
        One of ``test``, ``team`` or ``live``.
    with_file : bool
        Whether the file template must be configured.

    Returns
    -------
    NotifyClient
        Client using that key and the configured templates.
    """
    file_variable = EMAIL_WITH_FILE.variable
    return NotifyClient(
        api_key=required_variable(KEY_VARIABLES[key_type]),
        template_id=required_variable(EMAIL.variable),
        file_template_id=(
            required_variable(file_variable)
            if with_file
            else os.environ.get(file_variable)
        ),
    )


def confirm(prompt: str, expected: str) -> bool:
    """Ask the user to type an exact answer.

    Parameters
    ----------
    prompt : str
        Question to show.
    expected : str
        Answer that counts as yes.

    Returns
    -------
    bool
        Whether the typed answer matched.
    """
    return input(f"{prompt} ").strip() == expected


def preview(args: argparse.Namespace) -> None:
    """Print the rendered subject, reference and body for one recipient."""
    message = load_message(args.message)
    recipient: dict[str, str] = {}
    if args.recipients:
        rows = list(read_recipients(args.recipients).values())
        if not 1 <= args.row <= len(rows):
            sys.exit(f"--row must be between 1 and {len(rows)}")
        recipient = rows[args.row - 1]
    fields = ", ".join(
        f"{k} (default '{v}')" for k, v in message.recipient_fields.items()
    )
    email = personalise(message, recipient)
    print(f"Subject:   {email.subject}\nReference: {email.reference}")
    if fields:
        print(f"Recipient fields: {fields}")
    print(f"\n{email.body}")


def send(args: argparse.Namespace) -> None:
    """Send a message to everyone on the list who does not have it yet."""
    message = load_message(args.message)
    rows = read_recipients(args.recipients)
    recipients = list(rows)
    file = None
    if args.file:
        file = prepare_file(
            args.file,
            confirm_email=not args.no_email_check,
            retention_weeks=args.retention_weeks,
        )
        check = "off" if args.no_email_check else "on"
        print(
            f"File: {args.file.name} | Kept for {args.retention_weeks} weeks | "
            f"Email check before download: {check}"
        )
    client = make_client(args.key, with_file=file is not None)
    plan = plan_send(client, message, recipients)
    print(
        f"Key: {args.key} | Reference: {message.reference} | "
        f"Recipients: {len(recipients)} | Already sent: {plan.already_sent} | "
        f"To send now: {len(plan.to_send)}"
    )
    if args.dry_run or not plan.to_send:
        return
    if args.key == "live" and not args.yes:
        count = str(len(plan.to_send))
        if not confirm(f"Type {count} to send to {count} people:", count):
            sys.exit("Not sent.")

    result = send_all(client, message, plan.to_send, rows, file)
    if result.failed:
        failed_file = args.recipients.parent / f"failed-{message.reference}.csv"
        write_addresses(failed_file, result.failed)
        sys.exit(f"{len(result.failed)} addresses failed. See {failed_file}")


def setup(args: argparse.Namespace) -> None:
    """Create or complete the env file with checked keys and template IDs."""
    done = run_setup(
        args.env_file,
        ask=input,
        ask_secret=getpass.getpass,
        make_client=lambda key: NotifyClient(key, template_id=""),
    )
    if not done:
        sys.exit(1)


def check_setup(args: argparse.Namespace) -> None:
    """Check each Notify template exists and is set up as notify-mailer needs."""
    client = NotifyClient(required_variable(KEY_VARIABLES[args.key]), template_id="")
    failed = False
    for spec in TEMPLATES:
        template_id = os.environ.get(spec.variable, "")
        if not template_id:
            problems = [f"{spec.variable} is not set"]
        else:
            try:
                problems = template_problems(spec, client.template(template_id))
            except HTTPError as error:
                problems = [f"Notify could not return it ({error.status_code})"]
        if not problems:
            print(f"OK       {spec.name} ({spec.variable})")
            continue
        failed = True
        print(f"PROBLEM  {spec.name} ({spec.variable}): {'; '.join(problems)}")
        print(f"         Subject: {spec.subject}")
        print("         Message: " + spec.body.replace("\n", "\n                  "))
    print(
        "\nNotify's API cannot show the unsubscribe setting. For newsletters, "
        "check 'Add an unsubscribe link' is ticked on each template."
    )
    if failed:
        sys.exit(1)


def status(args: argparse.Namespace) -> None:
    """Print how many emails for a reference are in each delivery status."""
    counts = make_client(args.key).status_counts(args.reference)
    for state, count in sorted(counts.items()):
        print(f"{state}: {count}")
    print(f"total: {sum(counts.values())}")


def unsubscribe(args: argparse.Namespace) -> None:
    """Remove addresses in a Notify unsubscribe report from the recipient list."""
    recipients = read_addresses(args.recipients)
    leaving = read_addresses(args.report, column=args.column)
    keep, remove = split_unsubscribed(recipients, leaving)
    if not remove:
        print("No one in the report is on the recipient list.")
        return
    print("These addresses will be removed. Check for group addresses first:")
    print("\n".join(f"  {address}" for address in remove))
    if not args.yes and not confirm(f"Remove {len(remove)}? Type yes:", "yes"):
        sys.exit("Nothing removed.")
    write_addresses(args.recipients, keep)
    print(f"Removed {len(remove)}. {len(keep)} recipients left.")


def teams(args: argparse.Namespace) -> None:
    """Write the message as an HTML page to open and copy into Teams."""
    message = personalise(load_message(args.message), {})
    output = args.output or args.message.with_suffix(".teams.html")
    output.write_text(to_html_page(message), encoding="utf-8")
    print(f"Open {output} in a browser, select all, copy and paste into Teams.")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser with one sub-command per action.
    """
    parser = argparse.ArgumentParser(prog="notify-mailer", description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(required=True)

    def add_key(command: argparse.ArgumentParser) -> None:
        command.add_argument("--key", choices=KEY_VARIABLES, default="test")

    command = commands.add_parser("preview", help="show the rendered email")
    command.add_argument("message", type=Path)
    command.add_argument("--recipients", type=Path, help="fill fields from this list")
    command.add_argument("--row", type=int, default=1, help="recipient to show")
    command.set_defaults(run=preview)

    command = commands.add_parser("send", help="send to a recipient list")
    command.add_argument("message", type=Path)
    command.add_argument("--recipients", type=Path, default=Path("data/recipients.csv"))
    add_key(command)
    command.add_argument("--dry-run", action="store_true", help="count only")
    command.add_argument("--yes", action="store_true", help="skip live confirmation")
    command.add_argument("--file", type=Path, help="file to link from the email")
    command.add_argument(
        "--no-email-check",
        action="store_true",
        help="let anyone with the link download the file without entering an email",
    )
    command.add_argument("--retention-weeks", type=int, default=26)
    command.set_defaults(run=send)

    command = commands.add_parser("setup", help="set up keys and templates in .env")
    command.set_defaults(run=setup)

    command = commands.add_parser("check-setup", help="check the Notify templates")
    add_key(command)
    command.set_defaults(run=check_setup)

    command = commands.add_parser("status", help="count deliveries by status")
    command.add_argument("reference")
    add_key(command)
    command.set_defaults(run=status)

    command = commands.add_parser("unsubscribe", help="apply an unsubscribe report")
    command.add_argument("report", type=Path)
    command.add_argument("--recipients", type=Path, default=Path("data/recipients.csv"))
    command.add_argument("--column", default="email_address")
    command.add_argument("--yes", action="store_true", help="skip confirmation")
    command.set_defaults(run=unsubscribe)

    command = commands.add_parser("teams", help="write an HTML page for Teams")
    command.add_argument("message", type=Path)
    command.add_argument("--output", type=Path)
    command.set_defaults(run=teams)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the command line.

    Parameters
    ----------
    argv : list[str] | None
        Arguments to parse instead of ``sys.argv``.
    """
    args = build_parser().parse_args(argv)
    load_env_file(args.env_file)
    try:
        args.run(args)
    except ValueError as error:
        logger.error(str(error))
        sys.exit(1)
