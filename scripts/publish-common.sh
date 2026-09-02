#!/usr/bin/env bash
set -euo pipefail

source_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-joejulian/container-images}"
source_revision="${GITHUB_SHA:-$(git rev-parse HEAD)}"

require_github_actions_publish() {
  if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
    printf 'refusing to publish outside GitHub Actions\n' >&2
    exit 1
  fi
}

validate_release_tag() {
  local image_name="${1:?image name required}"
  local image_version="${2:?image version required}"

  if [[ "${GITHUB_REF_TYPE:-}" != "tag" ]]; then
    return 0
  fi

  local release_tag="${RELEASE_TAG_NAME:-}"
  if [[ -z "${release_tag}" || "${release_tag}" != */* ]]; then
    printf 'tag releases require an image-scoped release tag\n' >&2
    return 1
  fi

  local release_image="${release_tag%%/*}"
  local release_version="${release_tag#*/}"
  release_version="${release_version#v}"

  if [[ "${release_image}" != "${image_name}" ]]; then
    printf 'release tag image %s does not match image %s\n' "${release_image}" "${image_name}" >&2
    return 1
  fi
  if [[ "${release_version}" != "${image_version}" ]]; then
    printf 'release tag version %s does not match image version %s\n' "${release_version}" "${image_version}" >&2
    return 1
  fi
}

is_mutable_ref() {
  local image_ref="${1:?image ref required}"
  local tag="${image_ref##*:}"

  [[ "${tag}" == "latest" ]]
}

publish_ref_exists() {
  local image_ref="${1:?image ref required}"

  docker buildx imagetools inspect --raw "${image_ref}" >/dev/null 2>&1
}

annotate_published_ref() {
  local image_ref="${1:?image ref required}"

  docker buildx imagetools create \
    --annotation "index:org.opencontainers.image.source=${source_url}" \
    --annotation "index:org.opencontainers.image.revision=${source_revision}" \
    --annotation "manifest-descriptor:org.opencontainers.image.source=${source_url}" \
    --annotation "manifest-descriptor:org.opencontainers.image.revision=${source_revision}" \
    --tag "${image_ref}" \
    "${image_ref}" >/dev/null
}
