FROM ghcr.io/joejulian/container-images/node:26.12.1@sha256:33d001c867e40433d6f5fea81e404290601cc498361732f9696178cf7244a370 AS node

FROM ghcr.io/joejulian/container-images/android-build-box:1.29.0@sha256:bbec11c209707eeb081ac3356494dfc46489550061c9a9f8daae06a6dad3b53b

# renovate: datasource=custom.android-build-tools depName=android-build-tools versioning=semver
ARG ANDROID_BUILD_TOOLS_VERSION=37.0.0

# Keep Node and npm together and ahead of the upstream distro's older Node.
COPY --from=node /usr/local/ /opt/actions-node/
ENV PATH="/opt/actions-node/bin:${PATH}"
COPY Dockerfile /usr/local/share/android-actions-runner.Dockerfile

# Preserve Yarn's package repository while refreshing its rotated signing keys.
# Only these reviewed primary keys may enter this repository-specific keyring.
RUN curl --fail --silent --show-error --location --max-time 30 --retry 2 \
       https://dl.yarnpkg.com/debian/pubkey.gpg -o /var/tmp/actions-yarn-key.asc \
    && fingerprints="$(gpg --batch --show-keys --with-colons /var/tmp/actions-yarn-key.asc \
         | awk -F: '$1 == "pub" { primary=1; next } $1 == "fpr" && primary { print $10; primary=0 }')" \
    && test -n "$fingerprints" \
    && for fingerprint in $fingerprints; do \
         case "$fingerprint" in \
           72ECF46A56B4AD39C907BBB71646B01B86E50310|4EF8150F4F2D7DE44F1DFF0BB42879CC6B38E118) ;; \
           *) exit 1 ;; \
         esac; \
       done \
    && gpg --batch --dearmor --output /usr/share/keyrings/actions-yarn.gpg /var/tmp/actions-yarn-key.asc \
    && printf '%s\n' 'deb [signed-by=/usr/share/keyrings/actions-yarn.gpg] https://dl.yarnpkg.com/debian/ stable main' \
       > /etc/apt/sources.list.d/yarn.list \
    && rm /var/tmp/actions-yarn-key.asc \
    && apt-get -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o Acquire::Retries=2 update -qq

RUN printf 'y\n' | timeout 600 /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager "build-tools;${ANDROID_BUILD_TOOLS_VERSION}"
COPY tests/signing_fixture.py /var/tmp/runner-signing-fixture.py
RUN python3 /var/tmp/runner-signing-fixture.py \
    && rm /var/tmp/runner-signing-fixture.py

RUN node_version="$(sed -n 's#^FROM .*/node:\([^@]*\)@.*#\1#p' /usr/local/share/android-actions-runner.Dockerfile)" \
    && test -n "$node_version" \
    && test "$(node --version)" = "v${node_version}" \
    && npm --version \
    && test -x /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager \
    && test -f /opt/android-sdk/platforms/android-35/android.jar \
    && test -d /opt/android-sdk/ndk/latest \
    && base_version="$(sed -n 's#^FROM .*/android-build-box:\([^@]*\)@.*#\1#p' /usr/local/share/android-actions-runner.Dockerfile)" \
    && test -n "$base_version" \
    && printf '%s-node%s.buildtools.%s\n' "$base_version" "$(node --version | cut -c2-)" "${ANDROID_BUILD_TOOLS_VERSION}" \
       > /usr/local/share/android-actions-runner-version
