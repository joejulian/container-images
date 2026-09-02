#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/publish-common.sh
source "${script_dir}/publish-common.sh"

GITHUB_REF_TYPE=branch RELEASE_TAG_NAME=main \
  validate_release_tag plex-media-server-plexpass 1.43.4.10903-1

GITHUB_REF_TYPE=tag RELEASE_TAG_NAME=plex-media-server-plexpass/v1.43.4.10903-1 \
  validate_release_tag plex-media-server-plexpass 1.43.4.10903-1

if GITHUB_REF_TYPE=tag RELEASE_TAG_NAME=main \
  validate_release_tag plex-media-server-plexpass 1.43.4.10903-1 2>/dev/null; then
  printf 'accepted a non-image-scoped tag\n' >&2
  exit 1
fi

if GITHUB_REF_TYPE=tag RELEASE_TAG_NAME=another-image/v1.43.4.10903-1 \
  validate_release_tag plex-media-server-plexpass 1.43.4.10903-1 2>/dev/null; then
  printf 'accepted a tag for another image\n' >&2
  exit 1
fi

if GITHUB_REF_TYPE=tag RELEASE_TAG_NAME=plex-media-server-plexpass/v1.43.3.10896-1 \
  validate_release_tag plex-media-server-plexpass 1.43.4.10903-1 2>/dev/null; then
  printf 'accepted a tag with the wrong image version\n' >&2
  exit 1
fi
