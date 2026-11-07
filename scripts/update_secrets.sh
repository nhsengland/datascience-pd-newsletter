#!/usr/bin/env bash
# Copy Notify settings and recipient lists from this machine to GitHub secrets.
#
# Usage: scripts/update_secrets.sh test|team|live|codespaces
#
#   test        notify-test environment: NOTIFY_API_KEY_TEST
#   team        notify-team environment: NOTIFY_API_KEY_TEAM and data/team.csv
#   live        notify-live environment: NOTIFY_API_KEY_LIVE and data/recipients.csv
#   codespaces  repo Codespaces secrets: test and team keys and data/team.csv
#               (never the live key: live sends go through Actions for approval)
#
# Lists for Actions are compressed and split across NEWSLETTER_RECIPIENTS_1, _2, ...
# so they are not limited by the size of one secret.
#
# Keys and template IDs are read from .env. Run from the repo root.
# Needs the GitHub CLI (gh), logged in with admin rights on the repo.
set -euo pipefail

MAX_SECRET_BYTES=48000
# The send workflow passes NEWSLETTER_RECIPIENTS_1 to _20. Keep these in step.
MAX_CHUNKS=20
CHUNK_PREFIX=NEWSLETTER_RECIPIENTS_

env_value() {
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']$//"
}

require_value() {
  local value
  value=$(env_value "$1")
  if [[ -z "$value" ]]; then
    echo "$1 must be set in .env" >&2
    exit 1
  fi
  printf '%s' "$value"
}

check_list() {
  if [[ ! -f "$1" ]]; then
    echo "No recipient list at $1" >&2
    exit 1
  fi
  local count
  count=$(uv run python -c "
import sys
from pathlib import Path
from notify_mailer.recipients import read_addresses
print(len(read_addresses(Path(sys.argv[1]))))
" "$1")
  echo "$1: $count valid addresses, $(wc -c < "$1") bytes"
}

confirm() {
  local answer
  read -r -p "Update $1? Type yes: " answer
  [[ "$answer" == "yes" ]] || { echo "Nothing changed."; exit 1; }
}

set_list_chunks() {
  local environment=$1 list=$2 chunks
  chunks=$(mktemp -d)
  trap 'rm -rf "$chunks"' RETURN
  scripts/split_recipient_list.sh "$list" "$chunks"
  local files=("$chunks"/part*)
  if (( ${#files[@]} > MAX_CHUNKS )); then
    echo "$list needs ${#files[@]} secrets; the limit here is $MAX_CHUNKS" >&2
    exit 1
  fi

  local number=0
  for file in "${files[@]}"; do
    number=$((number + 1))
    gh secret set "$CHUNK_PREFIX$number" --env "$environment" < "$file"
  done

  local name
  for name in $(gh secret list --env "$environment" --json name --jq '.[].name'); do
    if [[ "$name" == NEWSLETTER_RECIPIENTS ]] ||
       [[ "$name" =~ ^${CHUNK_PREFIX}([0-9]+)$ && ${BASH_REMATCH[1]} -gt $number ]]; then
      gh secret delete "$name" --env "$environment"
    fi
  done
  echo "Stored $list in $number secret(s)."
}

update_environment() {
  local environment="notify-$1" key_name=$2 list=${3:-}
  local key template_id file_template_id
  key=$(require_value "$key_name")
  template_id=$(require_value NOTIFY_TEMPLATE_ID)
  [[ -z "$list" ]] || check_list "$list"
  confirm "the $environment environment"

  printf '%s' "$key" | gh secret set "$key_name" --env "$environment"
  gh variable set NOTIFY_TEMPLATE_ID --env "$environment" --body "$template_id"
  file_template_id=$(env_value NOTIFY_FILE_TEMPLATE_ID)
  if [[ -n "$file_template_id" ]]; then
    gh variable set NOTIFY_FILE_TEMPLATE_ID --env "$environment" --body "$file_template_id"
  fi
  [[ -z "$list" ]] || set_list_chunks "$environment" "$list"
  echo "Updated $environment."
}

update_codespaces() {
  local test_key team_key template_id list=data/team.csv
  test_key=$(require_value NOTIFY_API_KEY_TEST)
  team_key=$(require_value NOTIFY_API_KEY_TEAM)
  template_id=$(require_value NOTIFY_TEMPLATE_ID)
  check_list "$list"
  if (( $(wc -c < "$list") > MAX_SECRET_BYTES )); then
    echo "$list is too big for one Codespaces secret" >&2
    exit 1
  fi
  confirm "the repo Codespaces secrets (test key, team key, team list)"

  printf '%s' "$test_key" | gh secret set NOTIFY_API_KEY_TEST --app codespaces
  printf '%s' "$team_key" | gh secret set NOTIFY_API_KEY_TEAM --app codespaces
  printf '%s' "$template_id" | gh secret set NOTIFY_TEMPLATE_ID --app codespaces
  local file_template_id
  file_template_id=$(env_value NOTIFY_FILE_TEMPLATE_ID)
  if [[ -n "$file_template_id" ]]; then
    printf '%s' "$file_template_id" | gh secret set NOTIFY_FILE_TEMPLATE_ID --app codespaces
  fi
  gh secret set NEWSLETTER_TEAM_RECIPIENTS --app codespaces < "$list"
  echo "Updated Codespaces secrets. Restart open codespaces to pick them up."
}

case "${1:-}" in
  test) update_environment test NOTIFY_API_KEY_TEST ;;
  team) update_environment team NOTIFY_API_KEY_TEAM data/team.csv ;;
  live) update_environment live NOTIFY_API_KEY_LIVE data/recipients.csv ;;
  codespaces) update_codespaces ;;
  *) echo "Usage: $0 test|team|live|codespaces" >&2; exit 1 ;;
esac
