ARG ANDROID_IMAGE_VERSION=1.29.0

FROM docker.io/library/node:24.22.1-bookworm@sha256:6449e19d8184d84062525b6a7524def03146c2cb04a7f08b076680d0e8e4240a AS node

FROM ghcr.io/joejulian/container-images/android-build-box:${ANDROID_IMAGE_VERSION}@sha256:bbec11c209707eeb081ac3356494dfc46489550061c9a9f8daae06a6dad3b53b
ARG ANDROID_IMAGE_VERSION

# Keep Node and npm together and ahead of the upstream distro's older Node.
COPY --from=node /usr/local/ /opt/actions-node/
ENV PATH="/opt/actions-node/bin:${PATH}"

RUN test "$(node --version | cut -d. -f1)" = v24 \
    && npm --version \
    && test -x /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager \
    && test -f /opt/android-sdk/platforms/android-35/android.jar \
    && test -d /opt/android-sdk/ndk/latest \
    && printf '%s-node%s\n' "${ANDROID_IMAGE_VERSION}" "$(node --version | cut -c2-)" \
       > /usr/local/share/android-actions-runner-version
