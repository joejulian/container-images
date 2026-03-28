---
name: container-images-maintainer
description: Maintain the container-images monorepo when tasks involve image definitions, publish scripts, changed-image matrix behavior, GHCR release rules, KUTTL validation, or Renovate-managed Dockerfile pins.
---

# container-images Maintainer

Use this skill when working in `joejulian/container-images`.

## Focus Areas

- `images/<name>/image.json` defines name, type, registry path, platforms, and version extraction.
- `scripts/publish-build.sh` and `scripts/publish-mirror.sh` define the real publishing contract.
- `scripts/render-matrix.sh` controls changed-image selection for CI and release.
- `.github/workflows/ci.yml` and `.github/workflows/release.yml` should stay thin wrappers around the scripts.

## Workflow

1. Read the relevant `image.json` first.
2. If the image is `build`, read its Dockerfile and `scripts/build-local.sh`.
3. If the task changes tags, versioning, or publishing behavior, read `scripts/publish-build.sh` before editing workflows.
4. For behavior changes, write or update tests or script-level validation first when practical.
5. The exception is a true regression fix for already-observed broken behavior; in that case, fix the bug and then add or tighten the regression coverage.
6. After changes, run the smallest relevant validation set:
   - `./scripts/lint.sh`
   - `./scripts/build-local.sh images/<name>` for changed build images
   - `./scripts/run-kuttl.sh images/<name>` when that image has `tests/kuttl`

## Behavior Constraints

- Keep immutable release tags tied to the underlying application version.
- Do not introduce non-semver release tag schemes to represent rebuild-only changes.
- Use moving tags such as `latest` and `sha-*` for rebuild churn; keep fully versioned tags immutable.
- Add or keep mirrored images only when the upstream image is on Docker Hub, or when upstream tagging is non-semver and this repo can still map the image back to an application semver.
- Keep new Dockerfile-managed dependency pins Renovate-friendly with explicit annotations and simple `ARG` values.

## Review Checklist

- Does `image.json` still describe the image truthfully?
- Does `versionCommand` still return the application version expected for immutable tags?
- Do CI and release workflows still delegate to scripts instead of reimplementing logic?
- Does the change affect only changed images, or did matrix selection accidentally widen?
- If the image has KUTTL tests, do they still exercise the changed runtime path?
