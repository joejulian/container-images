#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

source_image="$(jq -r '.sourceImage' "${def}")"
dest_image="$(jq -r '.image' "${def}")"
latest_tag="$(jq -r '.latestTag // empty' "${def}")"
publish_tag() {
  local source_ref="$1"
  local dest_ref="$2"

  skopeo copy --all "docker://${source_ref}" "docker://${dest_ref}" >/dev/null
}

while IFS= read -r tag; do
  publish_tag "${source_image}:${tag}" "${dest_image}:${tag}"
done < <(jq -r '.tags[]' "${def}")

if [[ -n "${latest_tag}" ]]; then
  first_tag="$(jq -r '.tags[0]' "${def}")"
  publish_tag "${source_image}:${first_tag}" "${dest_image}:${latest_tag}"
fi
