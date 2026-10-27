#!/usr/bin/env bash
set -euo pipefail

find_latest_version_tag() {
  local source_image="$1"
  local prefix="$2"
  local pattern="${3:-^${prefix}[0-9]+(\.[0-9]+)+$}"
  local tags
  local latest

  if ! tags="$(crane ls "${source_image}")"; then
    return 1
  fi

  latest="$(
    printf '%s\n' "${tags}" \
      | grep -E -- "${pattern}" \
      | sort -V \
      | tail -n1 \
      || true
  )"
  [[ -n "${latest}" ]] || return 2
  printf '%s\n' "${latest}"
}

main() {
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

    if ! latest_version_tag="$(find_latest_version_tag "${source_image}" "${prefix}" "$(jq -r '.versionPattern // empty' "${def}")")"; then
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

}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
