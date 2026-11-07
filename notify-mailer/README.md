# notify-mailer

Send emails written in local Markdown files through [GOV.UK Notify](https://www.notifications.service.gov.uk/).

All wording lives in your repository. Notify holds two fixed templates, and each send fills one in.

## Notify set-up

The quickest way is:

```bash
notify-mailer setup
```

It creates `.env` if needed, asks for each API key (hidden as you paste) and checks it with Notify, then finds both templates in your service by their content and saves their IDs. If a template is missing, it shows exactly what to create and waits while you do it. It is safe to run again: it only asks for what is missing.

Notify's API cannot create templates or keys, so those are made in the [Notify portal](https://www.notifications.service.gov.uk/). The manual steps are:

1. Create a `.env` file in the folder you will run from. Never commit it.
   ```bash
   # Template IDS
   NOTIFY_TEMPLATE_ID=
   NOTIFY_FILE_TEMPLATE_ID=

   # API Keys
   NOTIFY_API_KEY_TEST=
   NOTIFY_API_KEY_TEAM=
   NOTIFY_API_KEY_LIVE=
   ```
2. **Templates → New template → Email**. Copy each one exactly:

   | Template name | Subject | Message | `.env` variable |
   |---|---|---|---|
   | notify-mailer email | `((subject))` | `((body))` | `NOTIFY_TEMPLATE_ID` |
   | notify-mailer email with file | `((subject))` | `((body))`, a blank line, then `((link_to_file))` | `NOTIFY_FILE_TEMPLATE_ID` |

   Tick **Add an unsubscribe link** on both if the emails are subscription emails, such as a newsletter. Save, then copy the template ID (shown under the template) into `.env`.
3. **API integration → Create an API key**. Add each key you need to `.env`:
   - **Test**: delivers nothing. Use it to try things out.
   - **Team and guest list**: sends only to members of your Notify team.
   - **Live**: sends to anyone. Only works once the service is live.
4. Check it all:
   ```bash
   notify-mailer check-setup
   ```
   Each template shows `OK`, or `PROBLEM` with the exact subject and message to fix it.

Settings can also come from environment variables, which take priority over `.env`.

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

## Sending files

Add `--file` to send a file with the email. Recipients get a link to download it, not an attachment.

```bash
notify-mailer send report.md --recipients team.csv --key team --file report.xlsx
```

- Files must be under 2MB and one of: CSV, DOC, DOCX, JPEG, JPG, JSON, ODT, PDF, PNG, RTF, TXT, XLSX. Save logs as `.txt`.
- By default, recipients must enter their email address before downloading. Keep this for anything personal, sensitive or OFFICIAL. `--no-email-check` turns it off.
- Files stay available for 26 weeks by default. Use `--retention-weeks` to choose 1 to 78.
- The file is read and checked once, before anything is sent. Notify needs it in every send request, so for large lists, consider hosting the file elsewhere and linking to it instead.

## Python

The same pieces work from Python, for example at the end of a pipeline:

```python
import os
from pathlib import Path

from notify_mailer import Message, NotifyClient, prepare_file

client = NotifyClient(
    api_key=os.environ["NOTIFY_API_KEY_TEAM"],
    template_id=os.environ["NOTIFY_TEMPLATE_ID"],
    file_template_id=os.environ["NOTIFY_FILE_TEMPLATE_ID"],
)
message = Message(
    subject="Monthly report ready",
    body="# Monthly report\n\nThe pipeline finished. The report is linked below.",
    reference="monthly-report-2026-11",
)
client.send("analyst@example.org", message, file=prepare_file(Path("report.xlsx")))
```

## Commands

```bash
notify-mailer setup                                 # set up .env: keys and templates
notify-mailer check-setup                           # check the Notify templates
notify-mailer preview MESSAGE [--recipients FILE --row N]  # show the rendered email
notify-mailer send MESSAGE --recipients FILE --key test|team|live [--dry-run] [--file FILE]
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
