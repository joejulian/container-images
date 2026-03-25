#!/usr/bin/env bash
set -euo pipefail

status=0
while IFS= read -r dir; do
  def="${dir}/image.json"
  jq -e '
    .name != null and
    (.type == "build" or .type == "mirror") and
    .image != null and
    .basePreference != null
  ' "${def}" >/dev/null || status=1

  kind="$(jq -r '.type' "${def}")"
  case "${kind}" in
    build)
      jq -e '.context != null and .dockerfile != null' "${def}" >/dev/null || status=1
      ;;
    mirror)
      jq -e '.sourceImage != null and (.tags | length) > 0' "${def}" >/dev/null || status=1
      ;;
  esac
done < <(./scripts/list-images.sh)

exit "${status}"

