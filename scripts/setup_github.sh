#!/usr/bin/env bash
# Create the GitHub environments the Notify workflows use, then copy secrets to them.
#
# Usage: scripts/setup_github.sh
#
# - notify-test and notify-team: no approval needed
# - notify-live: needs approval, and only runs from main. If it has no reviewers
#   yet, you become the reviewer. Existing reviewers are left alone.
#
# Safe to run again. Run from the repo root. Needs the GitHub CLI (gh), logged in
# with admin rights on the repo.
set -euo pipefail

repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
environments="repos/$repo/environments"

gh api -X PUT "$environments/notify-test" > /dev/null
gh api -X PUT "$environments/notify-team" > /dev/null
echo "Ready: notify-test, notify-team"

reviewers=$(gh api "$environments/notify-live" \
  --jq '[.protection_rules[]? | select(.type == "required_reviewers")] | length' \
  2> /dev/null || echo 0)
if [[ "$reviewers" == "0" ]]; then
  my_id=$(gh api user --jq .id)
  gh api -X PUT "$environments/notify-live" --input - > /dev/null <<EOF
{"reviewers": [{"type": "User", "id": $my_id}],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
  echo "Ready: notify-live, with you as reviewer"
else
  echo "Ready: notify-live already has reviewers, left unchanged"
fi

if ! gh api "$environments/notify-live/deployment-branch-policies" \
     --jq '.branch_policies[].name' | grep -qx main; then
  gh api -X POST "$environments/notify-live/deployment-branch-policies" -f name=main > /dev/null
fi
echo "notify-live only runs from main."

for target in test team live codespaces; do
  echo
  echo "== Secrets: $target"
  scripts/update_secrets.sh "$target" || echo "Skipped $target. Run scripts/update_secrets.sh $target later."
done
