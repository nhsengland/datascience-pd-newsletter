#!/usr/bin/env bash
# Compress a recipient list and split it into pieces small enough for GitHub secrets.
# scripts/join_recipient_secrets.sh reverses this.
#
# Usage: scripts/split_recipient_list.sh LIST OUTPUT_DIR
# Writes OUTPUT_DIR/part00, part01, ... in order.
set -euo pipefail

MAX_SECRET_BYTES=48000

list=${1:?Usage: $0 LIST OUTPUT_DIR}
output_dir=${2:?Usage: $0 LIST OUTPUT_DIR}
gzip -9 -c "$list" | base64 -w0 | split -b "$MAX_SECRET_BYTES" -d -a 2 - "$output_dir/part"
