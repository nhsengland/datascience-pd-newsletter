#!/usr/bin/env bash
# Rebuild a recipient list from the NEWSLETTER_RECIPIENTS_1, _2, ... environment
# variables, as written by scripts/split_recipient_list.sh and update_secrets.sh.
# Each piece is its own variable because Linux limits one variable to 128 KB.
#
# Usage: scripts/join_recipient_secrets.sh OUTPUT
set -euo pipefail

output=${1:?Usage: $0 OUTPUT}

joined=""
pieces=0
while true; do
  name="NEWSLETTER_RECIPIENTS_$((pieces + 1))"
  [[ -n "${!name:-}" ]] || break
  joined+="${!name}"
  pieces=$((pieces + 1))
done

if (( pieces == 0 )); then
  echo "No NEWSLETTER_RECIPIENTS_ secrets found. Run scripts/update_secrets.sh." >&2
  exit 1
fi
base64 -d <<< "$joined" | gunzip > "$output"
echo "Rebuilt the recipient list from $pieces piece(s)."
