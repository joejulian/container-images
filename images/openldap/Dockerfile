FROM registry.gitlab.com/joejulian/oci-arch:latest@sha256:0eb3e363d3dd7bf5cfbc099362b1b5de92f726478c38ce1bc18026d232de768f

RUN pacman-key --init && pacman-key --populate archlinux && \
    pacman -Syu --noconfirm --disable-sandbox --ignore filesystem \
      archlinux-keyring \
      db \
      openldap \
      perl && \
    pacman -Scc --noconfirm --disable-sandbox && \
    rm -rf /var/cache/pacman/pkg

VOLUME ["/config", "/slapd.d"]
EXPOSE 10389
CMD ["/usr/bin/slapd", "-u", "ldap", "-g", "ldap", "-h", "ldap://:10389", "-F", "/slapd.d", "-f", "/config/slapd.conf", "-d", "0x8100"]
