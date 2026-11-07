<img src='./docs/_assets/img/newsletter.png' align="right" alt="Newsletter logo: an envelope marked newsletter with wings" height="80" />

# NHS England Data Science Professional Development Newsletter

## About

A newsletter promoting professional development for data scientists at NHS England.

## Contributing to the newsletter

Have something to contribute to the newsletter? Easily suggest it to us using the "Issues" button on the repository, or [click here](https://github.com/nhsengland/datascience-pd-newsletter/issues/new?assignees=&labels=&projects=&template=suggest-some-newsletter-content-.md&title=). We welcome all suggestions and will do our best to include everything suitable to the newsletter.

## Creating the newsletter
Creating the next monthly newsletter? Here's how:
- Create a new branch with the title "month_year_newsletter"
- Open that branch up within GitHub codespaces
- Create a new subfolder to contain the new newsletter: docs/posts/YYYY_MM
- Copy and paste the index.css file into this folder (HTML rendering will not work otherwise- this is a workaround)
- Copy and paste the newsletter_template.qmd file into this folder (from the root folder), and rename to "newsletter.qmd"
- Replace the necessary parts in the YAML at the top of the file with the information for this month (title, date, description, authors)
- Replace the image address for the banner with the correct month. Images are found in docs/images.
- Check the newsletter renders as expected by following the instructions under [Developing](#developing)
- Start editing the file to add in all the content you want, checking periodically it's rendering as expected.
- Take a look at the [PD GitHub](https://github.com/nhsengland/PD_kanban_board/blob/main/PD%20Files/Resources/newsletter.md) for details on what to add to the newsletter.
- You can also update the wordle at the end of the newsletter going to [Custom Wordle](https://mywordle.strivemath.com/). Remember to keep the word short (5 letters) and related!
- When finished, create a PR for it to be reviewed and once approved and pushed, an action should kick off to render it so it can be shared.
- The link in the "about" section should be updated with the latest newsletter. Use this link to share the newsletter.
- See the "Distributing the newsletter" section below for details on how to share the newsletter.

## Distributing the newsletter
The newsletter email is sent through GOV.UK Notify with [notify-mailer](notify-mailer/README.md). You can send from your machine, a codespace, or GitHub Actions.

### One-off set-up
1. Install [uv](https://docs.astral.sh/uv/) (codespaces already have it), then run `uv sync` in the repo root.
2. Create a `.env` file in the repo root. It is gitignored. Never commit it.
   ```bash
   NOTIFY_TEMPLATE_ID=
   NOTIFY_API_KEY_TEST=
   NOTIFY_API_KEY_TEAM=
   NOTIFY_API_KEY_LIVE=
   ```
3. Put the recipient lists in `data/`, which is gitignored. Each is a CSV file with an `email` column:
   - `data/recipients.csv`: everyone who gets the newsletter
   - `data/team.csv`: the newsletter team, for test sends

The repo is public. Email addresses and keys must never be committed.

### Each month
1. Once the edition is published, copy last month's file in `emails/` to `emails/YYYY_MM.md`. Update `month`, `edition_url` and the bullet points, then add it to a PR. The checks make sure it renders.
2. Check the email:
   ```bash
   uv run notify-mailer preview emails/YYYY_MM.md
   ```
3. Apply unsubscribes (see below).
4. Send to the team and check it in your inbox:
   ```bash
   uv run notify-mailer send emails/YYYY_MM.md --key team --recipients data/team.csv
   ```
5. Send to everyone. Do a dry run first. The real send asks you to type the number of recipients.
   ```bash
   uv run notify-mailer send emails/YYYY_MM.md --key live --dry-run
   uv run notify-mailer send emails/YYYY_MM.md --key live
   ```
   If a send stops part way, run the same command again within 7 days. It skips everyone who already has the email.
6. Check delivery a few minutes later:
   ```bash
   uv run notify-mailer status newsletter-YYYY_MM --key live
   ```
7. Make the Teams post. Open the HTML file it creates, select all, copy, and paste into the Data Science General channel:
   ```bash
   uv run notify-mailer teams emails/YYYY_MM.md
   ```
8. Add the edition to the table on the [Confluence page](https://nhsd-confluence.digital.nhs.uk/spaces/DAT/pages/565791242/DS+PD+Newsletter+and+event+calendar).

To send from GitHub Actions instead of steps 4 and 5, run the **Send newsletter** workflow. Leave "dry run" ticked first, then run it again without. Live sends wait for a reviewer to approve.

### Writing the email
- Notify removes images and does not support bold or italic text. The tool rejects files that use them.
- Use `#` for headings, `*` for bullets and `[text](url)` for links. Link text should say where the link goes, not "click here".
- Notify adds a gap after a nested list, so put any item with sub-bullets last.
- The fixed wording is in `emails/_layout.md`.

### Unsubscribes
Notify adds an unsubscribe link to every email. Requests appear on the Notify dashboard for 90 days. Before each send:
1. Download the unsubscribe report from the dashboard.
2. Remove those people from the list. The command shows who will be removed and asks you to confirm. Check for group addresses, such as `england.datascience.assembly@nhs.net`, before confirming.
   ```bash
   uv run notify-mailer unsubscribe path/to/report.csv
   ```
   If it says the column is missing, pass the report's email column name with `--column`.
3. If you send from GitHub Actions, update the secrets (below).

### Updating GitHub secrets
GitHub Actions uses copies of the keys and lists, stored as secrets in the `notify-test`, `notify-team` and `notify-live` environments. After changing `.env` or a list, update them with the [GitHub CLI](https://cli.github.com/):
```bash
scripts/update_secrets.sh live   # or test, or team
```
Lists are compressed and split across up to 20 numbered secrets (`NEWSLETTER_RECIPIENTS_1`, `_2`, ...). That holds roughly 85,000 addresses. To allow more, add lines to the list step in `.github/workflows/send_newsletter.yml` and raise `MAX_CHUNKS` in the script.

### Codespaces
Codespaces get the test key, the team key and the team list as repo Codespaces secrets. A new codespace writes `data/team.csv` when it starts, so previews, team sends and the integration test work without a `.env` file. Update these secrets with:
```bash
scripts/update_secrets.sh codespaces
```
The live key is never stored as a Codespaces secret, because anyone with write access to the repo would get it. To send to everyone from a codespace, run the **Send newsletter** workflow, which waits for a reviewer to approve.

### Built With

- [Quarto](https://quarto.org/)
- [GitHub Actions](https://github.com/features/actions)

## Developing
We create the newsletter using .qmd files, which are markdown files with extra functionality provided by Quarto. Follow the instructions below to find out how to render your `.qmd` so you can see what it will look like once published.

Credit to [rocker-org](https://github.com/rocker-org/devcontainer-features/tree/main/src/quarto-cli) for making this possible.
**These instructions are specifically for running in GitHub codespaces. To run on your local machine I believe you would need to additonally install Quarto CLI, as well as the VSCode extension. I'm not sure if it would be possible on a corporate laptop.**

Once your GitHub codespace is set up, you can run in terminal:
`quarto preview path/to/file.qmd`. An example filepath is: `/workspaces/datascience-pd-newsletter/docs/about.qmd`

You can also run via `Ctrl+Shift+K`, or by clicking the 'Preview' button that should be in the top right of any `.qmd` file now. It will run the following line in terminal: `quarto preview /workspaces/datascience-pd-newsletter/docs/about.qmd --no-browser --no-watch-inputs`

`--no-browser` means it shouldn't automatically open a new tab with the page

`--no-watch-inputs` means it won't look for changes when you refresh.

I would recommend running it without the additional inputs. It will be quite handy to make changes on the file, then refresh the browser page and see them.

Regardless of which way you choose, it should prepare the preview and give you something like this: `Browse at http://localhost:4905/about.html` which you can click on to see the webpage.

## License

Distributed under a MIT License. _See [LICENSE.md](/LICENSE) for more information._
