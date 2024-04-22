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
- Copy and paste the newsletter_template.qmd file from the root folder, and rename to "newsletter.qmd"
- Replace the necessary parts in the YAML at the top of the file with the information for this month (title, date, description, authors)
- Replace the image address for the banner with the correct month
- Check the newsletter renders as expected by following the instructions under [Developing](#developing)
- Start editing the file to add in all the content you want, checking periodically it's rendering as expected.
- When finished, create a PR for it to be reviewed and once approved and pushed, an action should kick off to render it so it can be shared.

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
