FROM ghcr.io/joejulian/container-images/node:24.22.1@sha256:c804d2fc9b810eadd1c65a43bc7f486e5258b2d52e64d4d2a3e69592fefb9621 AS node

FROM ghcr.io/joejulian/container-images/android-build-box:1.29.0@sha256:bbec11c209707eeb081ac3356494dfc46489550061c9a9f8daae06a6dad3b53b

# Keep Node and npm together and ahead of the upstream distro's older Node.
COPY --from=node /usr/local/ /opt/actions-node/
ENV PATH="/opt/actions-node/bin:${PATH}"
COPY Dockerfile /usr/local/share/android-actions-runner.Dockerfile

RUN test "$(node --version | cut -d. -f1)" = v24 \
    && npm --version \
    && test -x /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager \
    && test -f /opt/android-sdk/platforms/android-35/android.jar \
    && test -d /opt/android-sdk/ndk/latest \
    && base_version="$(sed -n 's#^FROM .*/android-build-box:\([^@]*\)@.*#\1#p' /usr/local/share/android-actions-runner.Dockerfile)" \
    && test -n "$base_version" \
    && printf '%s-node%s\n' "$base_version" "$(node --version | cut -c2-)" \
       > /usr/local/share/android-actions-runner-version
