# Container Images

Monorepo for images published to `ghcr.io/joejulian/container-images/*`.

## Layout

- `images/<name>/image.json`: image definition
- `images/<name>/Dockerfile`: build context for locally-built images
- `images/<name>/tests/kuttl`: optional kuttl smoke tests kept next to the image
- `scripts/`: CI and release helpers

## Image Kinds

- `build`: build from a local Dockerfile and publish to GHCR
- `mirror`: copy an upstream image tag into GHCR

## Base Image Preference

New images should prefer bases in this order:

1. `scratch`
2. distroless
3. `alpine`
4. `archlinux`

When an Arch-based image is unavoidable, keep the published image version tied to the installed package version.
Every `build` image must define `versionCommand`, and the published tags must include that application version.

## Local Usage

```sh
./scripts/lint.sh
./scripts/render-matrix.sh all
```

To validate a single locally-built image:

```sh
./scripts/build-local.sh images/postfix
```

To run image-local smoke tests:

```sh
./scripts/run-kuttl.sh images/mosquitto
```

## Publishing Notes

Each published image is labeled with its source repository and revision.

GitHub Container Registry package visibility is managed separately from repository
visibility. For personal-account packages, newly published packages still default
to `private`; change visibility in the GitHub package settings UI when you need
anonymous pulls.
