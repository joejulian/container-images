# container-images Agent Notes

This repository builds and publishes OCI images from `images/<name>/` definitions to `ghcr.io/joejulian/container-images/*`.

## Repo Shape

- `images/<name>/image.json` is the source of truth for image metadata.
- `images/<name>/Dockerfile` exists only for `build` images.
- `scripts/` contains the real CI and release logic; read the scripts before changing the workflows.
- `.github/workflows/ci.yml` validates changed images, and `.github/workflows/release.yml` publishes changed images on `main` plus scheduled rebuilds.

## Working Rules

- Keep image versioning tied to the underlying application version. Do not invent extra immutable version tags that break strict semver ordering.
- `latest` and commit-derived tags may move; fully versioned application tags are immutable once published.
- If an image embeds another tool such as `fsyslog`, allow that dependency to auto-update in the Dockerfile, but do not change the immutable published version tag unless the application version changes.
- Use `image.json` plus `scripts/publish-build.sh` or `scripts/publish-mirror.sh` as the design boundary. Do not duplicate version/tag rules ad hoc in workflows.
- Prefer the documented base image order: `scratch`, distroless, `alpine`, then `archlinux`.

## Testing And Validation

- Default to test-first changes for behavior that can be expressed in repo tests or script checks.
- The exception is a true regression fix for already-observed broken behavior; fix it, then add or tighten the regression coverage.
- Run `./scripts/lint.sh` after changing image definitions, publish scripts, or metadata rules.
- Run `./scripts/build-local.sh images/<name>` for any changed `build` image.
- If an image has `tests/kuttl`, run `./scripts/run-kuttl.sh images/<name>` after a successful local build.
- When changing matrix logic or publish behavior, inspect `scripts/render-matrix.sh`, `scripts/build-local.sh`, and `scripts/publish-build.sh` together.

## CI And Release

- CI validates only changed image definitions on pull requests and pushes.
- Release publishes only the changed images on `main`; the nightly schedule rebuilds `build` images to pick up upstream package updates.
- GHCR publishing uses `GITHUB_TOKEN`; do not replace it with unrelated credentials or use it for Docker logins outside GitHub Actions.
- Package visibility is separate from repository visibility. Packages published from this repo are expected to allow anonymous pulls; if a newly published package lands private, fix the GHCR package visibility.

## Renovate

- Renovate config lives in `renovate.json5`.
- Regex managers are used for pinned values inside Dockerfiles, such as `ARG FSYSLOG_VERSION=...`.
- When adding a new pinned dependency intended for Renovate, annotate it explicitly and keep the version in a simple parseable form.

## Repo Skill

- For substantial work in this repo, read [`.codex/skills/container-images-maintainer/SKILL.md`](/home/jjulian/dev/container-images/.codex/skills/container-images-maintainer/SKILL.md) first.
