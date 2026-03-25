#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

image="$(jq -r '.image' "${def}")"
name="$(jq -r '.name' "${def}")"
context="$(jq -r '.context' "${def}")"
dockerfile="$(jq -r '.dockerfile' "${def}")"

docker buildx build --load -t "local/${name}:ci" -f "${context}/${dockerfile}" "${context}"

version_command="$(jq -r '.versionCommand // empty' "${def}")"
if [[ -n "${version_command}" ]]; then
  version="$(docker run --rm "local/${name}:ci" sh -lc "${version_command}")"
  printf '%s\n' "${image}:${version}"
fi
