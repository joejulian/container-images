#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

source_image="$(jq -r '.sourceImage' "${def}")"
dest_image="$(jq -r '.image' "${def}")"
latest_tag="$(jq -r '.latestTag // empty' "${def}")"
source_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-joejulian/container-images}"
sha_tag="${GITHUB_SHA:-$(git rev-parse HEAD)}"

mutate_image() {
  local ref="$1"
  crane mutate \
    --label "org.opencontainers.image.source=${source_url}" \
    --label "org.opencontainers.image.revision=${sha_tag}" \
    "${ref}" >/dev/null
}

while IFS= read -r tag; do
  crane copy "${source_image}:${tag}" "${dest_image}:${tag}"
  mutate_image "${dest_image}:${tag}"
done < <(jq -r '.tags[]' "${def}")

if [[ -n "${latest_tag}" ]]; then
  first_tag="$(jq -r '.tags[0]' "${def}")"
  crane copy "${dest_image}:${first_tag}" "${dest_image}:${latest_tag}"
  mutate_image "${dest_image}:${latest_tag}"
fi
