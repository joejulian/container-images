FROM registry.gitlab.com/joejulian/oci-arch:latest AS build

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

RUN sed -i '/^DisableSandbox$/d' /etc/pacman.conf && \
    sed -i '/^\[options\]$/a DisableSandbox' /etc/pacman.conf

RUN mkdir -p /build && chown alpm:alpm /build
COPY *.patch /build
WORKDIR /build
USER alpm
ENV HOME=/tmp

RUN git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si --noconfirm

RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" sphinx
RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" lmdb
RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" krb5
RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" perl-pod-pom-view-restructured
RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" cyrus-sasl-gssapi
RUN yay -S --noconfirm --mflags "--skippgpcheck --skipchecksums" cyrus-imapd

FROM registry.gitlab.com/joejulian/oci-arch:latest
VOLUME /config
VOLUME /data
COPY --from=build /tmp/.cache/yay/*/*.pkg.tar.zst /install/
COPY --from=build /go/bin/fsyslog /bin
COPY services /etc/services
RUN pacman -Syu --noconfirm --disable-sandbox --ignore filesystem && \
    pacman -U --noconfirm --disable-sandbox /install/* && \
    pacman -Sc --disable-sandbox --noconfirm && \
    rm -rf /var/cache/pacman/pkg
CMD ["fsyslog", "-command", "/usr/lib/cyrus/master"]
