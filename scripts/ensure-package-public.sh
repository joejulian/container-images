#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

dest_image="$(jq -r '.image' "${def}")"
registry_ref="${dest_image#ghcr.io/}"
owner="${registry_ref%%/*}"
package_name="${registry_ref#*/}"
encoded_name="$(jq -rn --arg v "${package_name}" '$v|@uri')"

gh api \
  --method PATCH \
  --header 'Accept: application/vnd.github+json' \
  "/users/${owner}/packages/container/${encoded_name}/visibility" \
  -f visibility=public >/dev/null
