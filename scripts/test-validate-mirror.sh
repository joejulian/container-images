#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
fixture="$(mktemp -d "${TMPDIR:-/tmp}/mirror-validation.XXXXXXXX")"
cleanup() {
  [[ -n "$fixture" && -d "$fixture" && -f "$fixture/.task-fixture" ]] || return 1
  local resolved
  resolved="$(realpath -e -- "$fixture")"
  case "$resolved" in
    */mirror-validation.????????) ;;
    *) return 1 ;;
  esac
  while IFS= read -r -d '' file; do
    case "$file" in
      "$resolved/.task-fixture"|"$resolved/bin/crane"|"$resolved/image/image.json") ;;
      *) return 1 ;;
    esac
  done < <(find "$resolved" -type f -print0)
  rm -r -- "$resolved"
}
trap cleanup EXIT
touch "$fixture/.task-fixture"
mkdir "$fixture/bin" "$fixture/image"
cat > "$fixture/bin/crane" <<'CRANE'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  digest) printf 'sha256:%064d\n' 1 ;;
  manifest)
    case "$FIXTURE_KIND" in
      index) printf '%s\n' '{"manifests":[{"platform":{"os":"linux","architecture":"amd64"}},{"platform":{"os":"linux","architecture":"arm64"}}]}' ;;
      *) printf '%s\n' '{"mediaType":"application/vnd.oci.image.manifest.v1+json"}' ;;
    esac ;;
  config)
    case "$FIXTURE_KIND" in
      direct) printf '%s\n' '{"os":"linux","architecture":"amd64"}' ;;
      malformed) printf '%s\n' '{"os":"linux"}' ;;
      *) exit 1 ;;
    esac ;;
  *) exit 1 ;;
esac
CRANE
chmod +x "$fixture/bin/crane"
export PATH="$fixture/bin:$PATH"
printf '%s\n' '{"sourceImage":"example.invalid/image","tags":["1.2.3"],"platforms":["linux/amd64"]}' > "$fixture/image/image.json"
FIXTURE_KIND=direct bash "$script_dir/validate-mirror.sh" "$fixture/image"
FIXTURE_KIND=index bash "$script_dir/validate-mirror.sh" "$fixture/image"
if FIXTURE_KIND=malformed bash "$script_dir/validate-mirror.sh" "$fixture/image" >/dev/null 2>&1; then
  printf 'accepted missing architecture\n' >&2; exit 1
fi
printf '%s\n' '{"sourceImage":"example.invalid/image","tags":["1.2.3"],"platforms":["linux/amd64","linux/arm64"]}' > "$fixture/image/image.json"
FIXTURE_KIND=index bash "$script_dir/validate-mirror.sh" "$fixture/image"
if FIXTURE_KIND=direct bash "$script_dir/validate-mirror.sh" "$fixture/image" >/dev/null 2>&1; then
  printf 'accepted missing required arm64 platform\n' >&2; exit 1
fi
printf 'Mirror platform validation tests passed\n'
