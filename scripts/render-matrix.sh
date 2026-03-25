#!/usr/bin/env bash
set -euo pipefail

mode="${1:-all}"
base_ref="${2:-}"
head_ref="${3:-HEAD}"

declare -a dirs=()

if [[ "${mode}" == "changed" && -n "${base_ref}" && "${base_ref}" != "0000000000000000000000000000000000000000" ]]; then
  mapfile -t dirs < <(
    git diff --name-only "${base_ref}" "${head_ref}" -- images \
      | awk -F/ 'NF >= 2 { print $1 "/" $2 }' \
      | sort -u
  )
else
  mapfile -t dirs < <(./scripts/list-images.sh)
fi

printf '{"include":['
first=1
for dir in "${dirs[@]}"; do
  [[ -f "${dir}/image.json" ]] || continue
  if [[ ${first} -eq 0 ]]; then
    printf ','
  fi
  first=0
  jq -c --arg dir "${dir}" '. + {dir: $dir}' "${dir}/image.json"
done
printf ']}\n'
