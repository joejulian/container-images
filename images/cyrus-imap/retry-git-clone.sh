#!/usr/bin/env bash
set -euo pipefail

url="${1:?repository URL required}"
destination="${2:?destination required}"

for attempt in 1 2 3; do
  if git -c http.version=HTTP/1.1 clone --depth 1 "${url}" "${destination}"; then
    exit 0
  fi

  if [[ -e "${destination}" ]]; then
    rm -r -- "${destination}"
  fi
  if (( attempt < 3 )); then
    sleep "$((attempt * 2))"
  fi
done

exit 1
