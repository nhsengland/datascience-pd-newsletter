#!/usr/bin/env bash
# In a codespace, write data/team.csv from the NEWSLETTER_TEAM_RECIPIENTS secret.
set -euo pipefail

if [[ -n "${NEWSLETTER_TEAM_RECIPIENTS:-}" ]]; then
  mkdir -p data
  printf '%s\n' "$NEWSLETTER_TEAM_RECIPIENTS" > data/team.csv
  echo "Wrote data/team.csv from the Codespaces secret."
fi
