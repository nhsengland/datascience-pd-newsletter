# notify-mailer

Send emails written in local Markdown files through [GOV.UK Notify](https://www.notifications.service.gov.uk/).

All wording lives in your repository. Notify holds one email template, and each send fills it in.

## Notify set-up

1. Create an email template with `((subject))` as the subject and `((body))` as the message.
2. Tick "Add an unsubscribe link" if the emails are subscription emails.
3. Create API keys. A test key delivers nothing, a team key sends only to your team, and a live key sends to anyone.

## Settings

Set these in the environment or in a `.env` file in the folder you run from. Never commit `.env`.

| Variable | Used for |
|---|---|
| `NOTIFY_TEMPLATE_ID` | The template above |
| `NOTIFY_API_KEY_TEST` | `--key test` (the default) |
| `NOTIFY_API_KEY_TEAM` | `--key team` |
| `NOTIFY_API_KEY_LIVE` | `--key live` |

## Message files

A message file is Markdown with YAML front matter. It needs a `subject`, either itself or from its layout.

```markdown
---
layout: _layout.md
month: November 2026
---
* First item
* Second item
```

A layout wraps the content. Its `${content}` field takes the message content, and other `${name}` fields take front matter values. `${stem}` is the message file name without `.md`.

```markdown
---
subject: Newsletter - ${month}
reference: newsletter-${stem}
---
# The ${month} newsletter is out

${content}
```

`reference` defaults to `${stem}`. It labels every email in one send, so it must not contain personal data.

Notify does not support images, bold or italic text, so files containing them are rejected. Headings (`#`, `##`), bullets, numbered lists, links, inset text (`^`) and horizontal lines work.

## Recipient lists

A CSV file with an `email` column. Addresses are trimmed, lower-cased and de-duplicated, keeping the first row. Other columns can be used for personalisation. Keep these files out of git, and only add columns you use.

## Personalisation

List the fields to fill per recipient under `recipient_fields`, in the message or its layout, with the value to use when a recipient's cell is blank or missing. Each field name must match a column header in the recipient list.

```markdown
---
subject: Newsletter - ${month}
recipient_fields:
  name: colleague
  organisation: the NHS
---
Hi ${name},

Thank you to everyone at ${organisation} who contributed.
```

- Fields can be used in the subject and body, but not in `reference`.
- Values are cleaned before use: characters that would add formatting, links or placeholders are removed, as are URL schemes and `www.`, so a value always appears as plain text.
- The message is checked with the defaults before anything is sent, so a field that is not declared stops the send.
- See how it looks for one recipient with `notify-mailer preview MESSAGE --recipients FILE --row N`. The Teams page uses the defaults.

## Commands

```bash
notify-mailer preview MESSAGE [--recipients FILE --row N]  # show the rendered email
notify-mailer send MESSAGE --recipients FILE --key test|team|live [--dry-run]
notify-mailer status REFERENCE --key test|team|live # count deliveries by status
notify-mailer unsubscribe REPORT --recipients FILE  # remove unsubscribed addresses
notify-mailer teams MESSAGE                         # HTML page to copy into Teams
```

`send` skips anyone who already has an email with the same reference, so a stopped send can be run again safely. Notify keeps records for 7 days, so re-run within that time. Live sends ask you to type the recipient count first. Logs never contain addresses. Rejected addresses are written to `failed-<reference>.csv` next to the recipient file.

## Development

```bash
uv run pytest                    # unit tests
uv run pytest -m integration     # real Notify calls with the test key
uv run ruff check . && uv run ruff format --check .
```
