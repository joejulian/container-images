#!/usr/bin/env bash
set -euo pipefail

source_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-joejulian/container-images}"
source_revision="${GITHUB_SHA:-$(git rev-parse HEAD)}"

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
