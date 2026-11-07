#!/usr/bin/env bash
# Copy Notify settings and a recipient list from this machine to a GitHub environment.
#
# Usage: scripts/update_secrets.sh test|team|live
#
#   test  NOTIFY_API_KEY_TEST
#   team  NOTIFY_API_KEY_TEAM and data/team.csv
#   live  NOTIFY_API_KEY_LIVE and data/recipients.csv
#
# Keys and NOTIFY_TEMPLATE_ID are read from .env. Run from the repo root.
# Needs the GitHub CLI (gh), logged in with admin rights on the repo.
set -euo pipefail

MAX_SECRET_BYTES=49152

case "${1:-}" in
  test) key_name=NOTIFY_API_KEY_TEST; list="" ;;
  team) key_name=NOTIFY_API_KEY_TEAM; list=data/team.csv ;;
  live) key_name=NOTIFY_API_KEY_LIVE; list=data/recipients.csv ;;
  *) echo "Usage: $0 test|team|live" >&2; exit 1 ;;
esac
environment="notify-$1"

env_value() {
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']$//"
}

key=$(env_value "$key_name")
template_id=$(env_value NOTIFY_TEMPLATE_ID)
if [[ -z "$key" || -z "$template_id" ]]; then
  echo "$key_name and NOTIFY_TEMPLATE_ID must both be set in .env" >&2
  exit 1
fi

if [[ -n "$list" ]]; then
  if [[ ! -f "$list" ]]; then
    echo "No recipient list at $list" >&2
    exit 1
  fi
  size=$(wc -c < "$list")
  if (( size > MAX_SECRET_BYTES )); then
    echo "$list is $size bytes; GitHub secrets hold at most $MAX_SECRET_BYTES" >&2
    exit 1
  fi
  count=$(uv run python -c "
import sys
from pathlib import Path
from notify_mailer.recipients import read_addresses
print(len(read_addresses(Path(sys.argv[1]))))
" "$list")
  echo "$list: $count valid addresses, $size bytes"
fi

read -r -p "Update secrets in the $environment environment? Type yes: " answer
[[ "$answer" == "yes" ]] || { echo "Nothing changed."; exit 1; }

printf '%s' "$key" | gh secret set "$key_name" --env "$environment"
gh variable set NOTIFY_TEMPLATE_ID --env "$environment" --body "$template_id"
if [[ -n "$list" ]]; then
  gh secret set NEWSLETTER_RECIPIENTS --env "$environment" < "$list"
fi
echo "Updated $environment."
