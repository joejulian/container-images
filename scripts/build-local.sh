#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
def="${dir}/image.json"

image="$(jq -r '.image' "${def}")"
name="$(jq -r '.name' "${def}")"
context="$(jq -r '.context' "${def}")"
dockerfile="$(jq -r '.dockerfile' "${def}")"
host_platform="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')"
platform="$(jq -r --arg host "${host_platform}" '
  (.platforms // ["linux/amd64"]) as $platforms
  | if ($platforms | index($host)) then $host else $platforms[0] end
' "${def}")"

docker buildx build --load --platform "${platform}" -t "local/${name}:ci" -f "${context}/${dockerfile}" "${context}"

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

printf '%s\n' "${image}:${version}"
