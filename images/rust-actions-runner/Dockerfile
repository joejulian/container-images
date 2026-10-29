FROM ghcr.io/joejulian/container-images/node:26.13.0@sha256:0b5bfd674a92f66119d5d4b173849bb9c17aba0f3a8db774cd2c742cb4591d0e AS node

# GNU Bookworm builds must run on a Bookworm application base. An Alpine/musl
# toolchain or a newer distribution would change that binary compatibility.
FROM rust:1.99.1-bookworm@sha256:48b7f435b8fc6378ce43b44f15e3a47fd8919b2825f835c39bd4bd3da50af5b8

COPY --from=node /usr/local/ /opt/actions-node/
ENV PATH="/opt/actions-node/bin:${PATH}"

# Tests own their broker processes; no installation-time daemon may start.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod 0755 /usr/sbin/policy-rc.d \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
         python3 libudev-dev mosquitto mosquitto-clients skopeo \
         qemu-user-static gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
    && rm -r /var/lib/apt/lists/* \
    && rustup component add rustfmt clippy \
    && rustup target add aarch64-unknown-linux-gnu \
    && chmod -R go-w "$RUSTUP_HOME" /usr/local/cargo \
    && useradd --create-home --uid 1000 --user-group builder \
    && install -d -o builder -g builder -m 0700 /home/builder/.cargo \
    && printf '%s-node%s\n' "$(rustc --version | cut -d ' ' -f 2)" \
         "$(node -p process.versions.node)" > /usr/local/share/rust-actions-runner-version

ENV HOME=/home/builder \
    CARGO_HOME=/home/builder/.cargo \
    CARGO_INCREMENTAL=0 \
    CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc

COPY --chmod=0755 tests/smoke.sh /usr/local/libexec/rust-actions-smoke
USER 1000:1000
WORKDIR /home/builder
RUN /usr/local/libexec/rust-actions-smoke
CMD ["/bin/bash"]
