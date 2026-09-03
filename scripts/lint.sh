#!/usr/bin/env bash
set -euo pipefail

status=0
while IFS= read -r dir; do
  def="${dir}/image.json"
  jq -e '
    .name != null and
    (.type == "build" or .type == "mirror") and
    .image != null and
    .basePreference != null and
    (.platforms == null or ((.platforms | type) == "array" and (.platforms | length) > 0))
  ' "${def}" >/dev/null || status=1

  kind="$(jq -r '.type' "${def}")"
  case "${kind}" in
    build)
      jq -e '.context != null and .dockerfile != null and .versionCommand != null' "${def}" >/dev/null || status=1
      dockerfile_path="$(jq -r '.context + "/" + .dockerfile' "${def}")"
      if grep -Eq '^FROM[[:space:]].*\$\{' "${dockerfile_path}"; then
        printf 'variable-composed FROM image is not Renovate-manageable: %s\n' "${dockerfile_path}" >&2
        status=1
      fi
      if grep -Eq '^FROM[[:space:]]+registry\.gitlab\.com/joejulian/oci-arch:' "${dockerfile_path}" &&
        ! grep -q 'DisableDownloadTimeout' "${dockerfile_path}"; then
        printf 'Arch image must disable pacman download timeouts: %s\n' "${dockerfile_path}" >&2
        status=1
      fi
      ;;
    mirror)
      jq -e '.sourceImage != null and (.tags | length) > 0' "${def}" >/dev/null || status=1
      ;;
  esac
done < <(./scripts/list-images.sh)

./scripts/test-publish-common.sh || status=1

exit "${status}"
