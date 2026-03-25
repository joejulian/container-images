#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

source_image="$(jq -r '.sourceImage' "${def}")"
dest_image="$(jq -r '.image' "${def}")"
latest_tag="$(jq -r '.latestTag // empty' "${def}")"

while IFS= read -r tag; do
  crane copy "${source_image}:${tag}" "${dest_image}:${tag}"
done < <(jq -r '.tags[]' "${def}")

if [[ -n "${latest_tag}" ]]; then
  first_tag="$(jq -r '.tags[0]' "${def}")"
  crane copy "${dest_image}:${first_tag}" "${dest_image}:${latest_tag}"
fi

