#!/usr/bin/env bash
set -euo pipefail

dir="${1:?image dir required}"
tests_dir="${dir}/tests/kuttl"

if [[ ! -d "${tests_dir}" ]]; then
  exit 0
fi

kubectl kuttl test "${tests_dir}" --timeout 120 --report-format json

