#!/usr/bin/env bash
set -euo pipefail

find_latest_version_tag() {
  local source_image="$1"

  crane ls "${source_image}" \
    | grep -E '^[0-9]+(\.[0-9]+)+$' \
    | sort -V \
    | tail -n1
}

while IFS= read -r dir; do
  def="${dir}/image.json"
  if [[ "$(jq -r '.type' "${def}")" != "mirror" ]]; then
    continue
  fi

  source_image="$(jq -r '.sourceImage' "${def}")"
  latest_version_tag="$(find_latest_version_tag "${source_image}")"
  [[ -n "${latest_version_tag}" ]] || continue

  updated="$(
    jq --arg latest "${latest_version_tag}" '
      .tags |= map(
        if test("^[0-9]+(\\.[0-9]+)+$") then
          $latest
        else
          .
        end
      )
    ' "${def}"
  )"

  if [[ "${updated}" != "$(cat "${def}")" ]]; then
    printf '%s\n' "${updated}" > "${def}"
  fi
done < <(./scripts/list-images.sh)
