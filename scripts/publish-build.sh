#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Shared package metadata keeps GHCR linked to the correct repository.
source "${script_dir}/publish-common.sh"

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
sha_short="$(printf '%s' "${sha_tag}" | cut -c1-12)"

docker build \
  --label "org.opencontainers.image.source=${source_url}" \
  --label "org.opencontainers.image.revision=${sha_tag}" \
  -t "local/${name}:ci" \
  -f "${context}/${dockerfile}" \
  "${context}"

tags=(
  "${image}:${latest_tag}"
  "${image}:sha-${sha_short}"
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

while IFS= read -r static_tag; do
  [[ -n "${static_tag}" ]] || continue
  tags+=("${image}:${static_tag}")
done < <(jq -r '.staticTags[]? // empty' "${def}")

tag_args=()
for tag in "${tags[@]}"; do
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
if existing_manifest="$(docker buildx imagetools inspect --raw "${version_ref}" 2>/dev/null)"; then
  missing_platforms=()
  for platform in "${required_platforms[@]}"; do
    IFS=/ read -r platform_os platform_arch platform_variant platform_extra <<< "${platform}"
    if [[ -n "${platform_extra:-}" || -z "${platform_os}" || -z "${platform_arch}" ]]; then
      printf 'invalid platform %s for image %s\n' "${platform}" "${name}" >&2
      exit 1
    fi

    if ! jq -e \
      --arg os "${platform_os}" \
      --arg arch "${platform_arch}" \
      --arg variant "${platform_variant:-}" \
      '
        if .manifests then
          any(.manifests[]?.platform?;
            .os == $os and
            .architecture == $arch and
            ($variant == "" or .variant == $variant))
        else
          .os == $os and
          .architecture == $arch and
          ($variant == "" or .variant == $variant)
        end
      ' <<< "${existing_manifest}" >/dev/null; then
      missing_platforms+=("${platform}")
    fi
  done

  if [[ ${#missing_platforms[@]} -eq 0 ]]; then
    printf 'version tag %s already exists with all required platforms, leaving it unchanged\n' "${version_ref}"
    exit 0
  fi

  printf 'version tag %s exists but is missing required platforms: %s\n' \
    "${version_ref}" "${missing_platforms[*]}"
  printf 'recreating %s from %s:sha-%s\n' "${version_ref}" "${image}" "${sha_short}"
fi

docker buildx imagetools create \
  --tag "${version_ref}" \
  "${image}:sha-${sha_short}"

annotate_published_ref "${version_ref}"
