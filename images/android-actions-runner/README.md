# Android Actions job image

The versioned Android build-box base provides SDK 35, the NDK, Java, and native
build tools. A pinned Node 24 distribution supplies Node and npm together for
Actions workflows that require that major version. Java setup actions can select
the application's required JDK independently.

The immutable release version combines the actual Android base and Node versions,
for example `1.29.0-node24.22.1`. Updating either input produces a distinct version
without overwriting an existing tag. Dockerfile dependency pins remain managed
by Renovate. Use a version tag and digest in runner labels.

The image intentionally supports amd64: this upstream Android SDK/NDK bundle is
an amd64 toolchain. Build checks verify Node 24, npm, SDK command-line tools,
platform 35, and the NDK before publication. The inherited Yarn APT repository
uses its current public certificates in a repository-specific keyring, restricted
to reviewed primary fingerprints. Every build checks authenticated package-index
refreshes, including future signing-subkey changes. Validate the consuming application's
normal unsigned build before changing production runner labels.
