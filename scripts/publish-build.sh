#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Shared package metadata keeps GHCR linked to the correct repository.
source "${script_dir}/publish-common.sh"
require_github_actions_publish

dir="${1:?image dir required}"
def="${dir}/image.json"

name="$(jq -r '.name' "${def}")"
image="$(jq -r '.image' "${def}")"
context="$(jq -r '.context' "${def}")"
dockerfile="$(jq -r '.dockerfile' "${def}")"
latest_tag="$(jq -r '.latestTag // "latest"' "${def}")"
mapfile -t required_platforms < <(jq -r '(.platforms // ["linux/amd64"])[]' "${def}")
platforms="$(IFS=,; printf '%s' "${required_platforms[*]}")"
sha_tag="${GITHUB_SHA:-$(git rev-parse HEAD)}"

docker build \
  --label "org.opencontainers.image.source=${source_url}" \
  --label "org.opencontainers.image.revision=${sha_tag}" \
  -t "local/${name}:ci" \
  -f "${context}/${dockerfile}" \
  "${context}"

tags=(
  "${image}:${latest_tag}"
)

version_command="$(jq -r '.versionCommand // empty' "${def}")"
if [[ -z "${version_command}" ]]; then
  printf 'build image %s is missing versionCommand\n' "${name}" >&2
  exit 1
fi

version="$(docker run --rm "local/${name}:ci" sh -lc "${version_command}")"
if [[ -z "${version}" ]]; then
  printf 'build image %s returned an empty version\n' "${name}" >&2
  exit 1
fi

if [[ -n "${RELEASE_TAG_NAME:-}" ]]; then
  release_image="${RELEASE_TAG_NAME%%/*}"
  release_version="${RELEASE_TAG_NAME#*/}"
  release_version="${release_version#v}"

  if [[ "${release_image}" != "${name}" ]]; then
    printf 'release tag image %s does not match image %s\n' "${release_image}" "${name}" >&2
    exit 1
  fi
  if [[ "${release_version}" != "${version}" ]]; then
    printf 'release tag version %s does not match image version %s\n' "${release_version}" "${version}" >&2
    exit 1
  fi
fi

while IFS= read -r static_tag; do
  [[ -n "${static_tag}" ]] || continue
  tags+=("${image}:${static_tag}")
done < <(jq -r '.staticTags[]? // empty' "${def}")

tag_args=()
for tag in "${tags[@]}"; do
  if ! is_mutable_ref "${tag}" && publish_ref_exists "${tag}"; then
    printf 'immutable image tag %s already exists; not publishing it again\n' "${tag}"
    continue
  fi
  tag_args+=(-t "${tag}")
done

docker buildx build --push \
  --platform "${platforms}" \
  --label "org.opencontainers.image.source=${source_url}" \
  --label "org.opencontainers.image.revision=${sha_tag}" \
  "${tag_args[@]}" \
  -f "${context}/${dockerfile}" \
  "${context}"

for tag in "${tags[@]}"; do
  annotate_published_ref "${tag}"
done

version_ref="${image}:${version}"
if publish_ref_exists "${version_ref}"; then
  printf 'version tag %s already exists; immutable tags are never recreated\n' "${version_ref}"
  exit 0
fi

docker buildx imagetools create \
  --tag "${version_ref}" \
  "${image}:${latest_tag}"

annotate_published_ref "${version_ref}"
