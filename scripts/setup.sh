#!/usr/bin/env bash
# One-off set-up for someone who will send the newsletter. Run from the repo root.
#
# 1. Installs the Python tools
# 2. Sets up .env: API keys and Notify template IDs, checked against Notify
# 3. Creates empty recipient lists in data/ if they are missing
# 4. Optionally sets up GitHub environments and secrets (needs repo admin)
#
# Safe to run again: it only asks for what is missing.
# In a codespace, keys come from Codespaces secrets, so you only need step 1.
set -euo pipefail

echo "== Installing tools"
uv sync

echo
echo "== Notify keys and templates"
uv run notify-mailer setup || echo "Set-up is not finished. Run scripts/setup.sh again when ready."

echo
echo "== Recipient lists"
mkdir -p data
for list in data/team.csv data/recipients.csv; do
  if [[ -f "$list" ]]; then
    echo "Found $list"
  else
    printf 'email\n' > "$list"
    echo "Created $list. Add one address per line under the 'email' header."
  fi
done

echo
read -r -p "Set up GitHub environments and secrets now? Needs repo admin. [y/N] " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
  scripts/setup_github.sh
else
  echo "Skipped. Run scripts/setup_github.sh later."
fi

echo
echo "Done. Try: uv run notify-mailer preview emails/2026_10.md"
