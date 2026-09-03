FROM registry.gitlab.com/joejulian/oci-arch:latest@sha256:0eb3e363d3dd7bf5cfbc099362b1b5de92f726478c38ce1bc18026d232de768f AS build

RUN sed -i '/^ParallelDownloads =/a DisableDownloadTimeout' /etc/pacman.conf

RUN pacman-key --init && pacman-key --populate archlinux

RUN pacman -Syu --needed --noconfirm --ignore filesystem \
      archlinux-keyring \
      base-devel \
      git \
      go \
      mariadb-libs \
      perl-module-install \
      python-pip \
      sudo

# renovate: datasource=git-tags depName=gitlab.com/joejulian/fsyslog versioning=semver
ARG FSYSLOG_VERSION=v0.4.0
RUN GO111MODULE=on GOPATH=/go GOBIN=/go/bin go install gitlab.com/joejulian/fsyslog@"${FSYSLOG_VERSION}"

COPY alpm.sudo /etc/sudoers.d/alpm
RUN chmod 400 /etc/sudoers.d/alpm
RUN chage -E -1 alpm

RUN sed -i '/^DisableSandbox$/d' /etc/pacman.conf && \
    sed -i '/^\[options\]$/a DisableSandbox' /etc/pacman.conf

RUN mkdir -p /build && chown alpm:alpm /build
COPY *.patch /build
WORKDIR /build

RUN pacman -S --noconfirm \
      clamav \
      cunit \
      cyrus-sasl-gssapi \
      krb5 \
      libchardet \
      libwslay \
      lmdb \
      perl-pod-pom \
      postgresql-libs \
      rsync \
      shapelib \
      unixodbc \
      xapian-core \
      zlib
RUN pacman -T xxd >/dev/null || pacman -S --noconfirm tinyxxd

RUN runuser -u alpm -- bash -lc "export HOME=/tmp && cd /build && git clone https://aur.archlinux.org/sphinx.git && cd sphinx && makepkg -A --noconfirm --skippgpcheck --skipchecksums" && \
    find /build/sphinx -maxdepth 1 -name '*.pkg.tar.*' -exec pacman -U --noconfirm {} +
RUN pacman -S --noconfirm \
      cmake \
      doxygen \
      gobject-introspection \
      gtk-doc \
      ninja \
      python-gobject \
      vala
RUN runuser -u alpm -- bash -lc "export HOME=/tmp && cd /build && git clone https://aur.archlinux.org/libical3.git && cd libical3 && makepkg -A --noconfirm --skippgpcheck --skipchecksums" && \
    find /build/libical3 -maxdepth 1 -name '*.pkg.tar.*' -exec pacman -U --noconfirm {} +
RUN runuser -u alpm -- bash -lc "export HOME=/tmp && cd /build && git clone https://aur.archlinux.org/perl-pod-pom-view-restructured.git && cd perl-pod-pom-view-restructured && makepkg -A --noconfirm --skippgpcheck --skipchecksums" && \
    find /build/perl-pod-pom-view-restructured -maxdepth 1 -name '*.pkg.tar.*' -exec pacman -U --noconfirm {} +
RUN runuser -u alpm -- bash -lc "export HOME=/tmp && cd /build && git clone https://aur.archlinux.org/cyrus-imapd.git && cd cyrus-imapd && makepkg -A --noconfirm --skippgpcheck --skipchecksums --nocheck" && \
    find /build/cyrus-imapd -maxdepth 1 -name '*.pkg.tar.*' -exec pacman -U --noconfirm {} +

FROM registry.gitlab.com/joejulian/oci-arch:latest@sha256:0eb3e363d3dd7bf5cfbc099362b1b5de92f726478c38ce1bc18026d232de768f
RUN sed -i '/^ParallelDownloads =/a DisableDownloadTimeout' /etc/pacman.conf
VOLUME /config
VOLUME /data
COPY --from=build /build/*/*.pkg.tar.* /install/
COPY --from=build /go/bin/fsyslog /bin
COPY services /etc/services
RUN pacman -Syu --noconfirm --disable-sandbox --ignore filesystem && \
    pacman -U --noconfirm --disable-sandbox /install/* && \
    pacman -Sc --disable-sandbox --noconfirm && \
    rm -rf /var/cache/pacman/pkg
CMD ["fsyslog", "-command", "/usr/lib/cyrus/master"]
