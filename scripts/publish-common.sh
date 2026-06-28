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
