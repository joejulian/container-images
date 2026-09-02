FROM registry.gitlab.com/joejulian/oci-arch:latest

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
