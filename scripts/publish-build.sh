#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

name="$(jq -r '.name' "${def}")"
image="$(jq -r '.image' "${def}")"
context="$(jq -r '.context' "${def}")"
dockerfile="$(jq -r '.dockerfile' "${def}")"
latest_tag="$(jq -r '.latestTag // "latest"' "${def}")"
sha_tag="${GITHUB_SHA:-$(git rev-parse HEAD)}"
sha_short="$(printf '%s' "${sha_tag}" | cut -c1-12)"

docker build -t "local/${name}:ci" -f "${context}/${dockerfile}" "${context}"

tags=(
  "${image}:${latest_tag}"
  "${image}:sha-${sha_short}"
)

version_command="$(jq -r '.versionCommand // empty' "${def}")"
if [[ -n "${version_command}" ]]; then
  version="$(docker run --rm "local/${name}:ci" sh -lc "${version_command}")"
  tags+=("${image}:${version}")
fi

while IFS= read -r static_tag; do
  [[ -n "${static_tag}" ]] || continue
  tags+=("${image}:${static_tag}")
done < <(jq -r '.staticTags[]? // empty' "${def}")

tag_args=()
for tag in "${tags[@]}"; do
  tag_args+=(-t "${tag}")
done

docker buildx build --push "${tag_args[@]}" -f "${context}/${dockerfile}" "${context}"
