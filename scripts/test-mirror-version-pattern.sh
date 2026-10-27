#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/update-mirror-tags.sh"
crane() { printf '%s\n' 8.0.32 8.0.34 8.2.8 9.0.1; }
[[ "$(find_latest_version_tag unused '' '^8[.]0[.][0-9]+$')" == 8.0.34 ]]
[[ "$(find_latest_version_tag unused '')" == 9.0.1 ]]
if find_latest_version_tag unused '' '^7[.]' >/dev/null; then
  echo 'accepted a missing release line' >&2
  exit 1
fi
