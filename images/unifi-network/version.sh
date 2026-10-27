#!/bin/sh
set -eu
grep -oE '[0-9]+\.[0-9]+\.[0-9]+' /build_version | head -n 1
