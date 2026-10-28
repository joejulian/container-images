#!/usr/bin/env bash
set -euo pipefail

def="${1:?image definition directory required}/image.json"
source_image="$(jq -er '.sourceImage' "$def")"
while IFS= read -r tag; do
  reference="${source_image}:${tag}"
  crane digest "$reference" >/dev/null
  manifest="$(crane manifest "$reference")"
  if jq -e '.manifests | type == "array"' <<< "$manifest" >/dev/null; then
    platforms="$(jq -c '[.manifests[].platform | select(.os != null and .architecture != null)]' <<< "$manifest")"
  else
    # A single-platform OCI/Docker manifest keeps architecture in its config.
    config="$(crane config "$reference")"
    platforms="$(jq -ec '[{os: .os, architecture: .architecture, variant: .variant}] | select(.[0].os != null and .[0].architecture != null)' <<< "$config")"
  fi
  while IFS= read -r required; do
    if ! jq -e --arg required "$required" '
      ($required | split("/")) as $parts
      | any(.[]; .os == $parts[0] and .architecture == $parts[1]
          and (($parts | length) < 3 or .variant == $parts[2]))
    ' <<< "$platforms" >/dev/null; then
      printf 'source image %s does not provide required platform %s\n' "$reference" "$required" >&2
      exit 1
    fi
  done < <(jq -r '.platforms[]?' "$def")
done < <(jq -r '.tags[]' "$def")
