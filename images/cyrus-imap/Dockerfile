FROM archlinux:latest AS build

RUN pacman -Syu --needed --noconfirm --ignore filesystem \
      archlinux-keyring \
      base-devel \
      git \
      go \
      perl-module-install \
      python-pip \
      sudo

RUN GO111MODULE=on GOPATH=/go GOBIN=/go/bin go install gitlab.com/joejulian/fsyslog@v0.3.1

COPY alpm.sudo /etc/sudoers.d/alpm
RUN chmod 400 /etc/sudoers.d/alpm

RUN mkdir -p /build && chown alpm:alpm /build
COPY *.patch /build
WORKDIR /build
USER alpm
ENV HOME=/tmp

RUN sudo sed -i '/^DisableSandbox$/d' /etc/pacman.conf && \
    sudo sed -i '/^\[options\]$/a DisableSandbox' /etc/pacman.conf

RUN cat /etc/pam.d/sudo && ls /etc/pam.d/ && sudo id
RUN git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si --noconfirm

RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums sphinx
RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums lmdb
RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums krb5
RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums perl-pod-pom-view-restructured
RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums cyrus-sasl-gssapi
RUN yay -S --noconfirm --mflags --skippgpcheck --mflags --skipchecksums cyrus-imapd

FROM archlinux:latest
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
