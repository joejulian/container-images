#!/usr/bin/env bash
set -euo pipefail

find_latest_version_tag() {
  local source_image="$1"
  local prefix="$2"
  local tags
  local latest

  if ! tags="$(crane ls "${source_image}")"; then
    return 1
  fi

  latest="$(
    printf '%s\n' "${tags}" \
      | grep -E "^${prefix}[0-9]+(\.[0-9]+)+$" \
      | sort -V \
      | tail -n1 \
      || true
  )"
  [[ -n "${latest}" ]] || return 2
  printf '%s\n' "${latest}"
}

while IFS= read -r dir; do
  def="${dir}/image.json"
  if [[ "$(jq -r '.type' "${def}")" != "mirror" ]]; then
    continue
  fi

  source_image="$(jq -r '.sourceImage' "${def}")"
  if jq -e '.tags[] | select(test("^v[0-9]+(\\.[0-9]+)+$"))' "${def}" >/dev/null; then
    prefix="v"
  else
    prefix=""
  fi

  if ! latest_version_tag="$(find_latest_version_tag "${source_image}" "${prefix}")"; then
    printf 'skipping %s: no matching semver tags found for %s\n' "${dir}" "${source_image}" >&2
    continue
  fi

  updated="$(
    jq --arg latest "${latest_version_tag}" --arg prefix "${prefix}" '
      .tags |= map(
        if test("^" + $prefix + "[0-9]+(\\.[0-9]+)+$") then
          $latest
        else
          .
        end
      )
    ' "${def}"
  )"

  if [[ "$(jq -c '.tags' <<< "${updated}")" != "$(jq -c '.tags' "${def}")" ]]; then
    printf '%s\n' "${updated}" > "${def}"
  fi
done < <(./scripts/list-images.sh)
