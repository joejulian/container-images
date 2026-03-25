FROM archlinux:latest

RUN pacman -Syu --needed --noconfirm \
        rspamd \
    && pacman -Scc --noconfirm \
    && rm /var/cache/pacman/pkg/*

CMD mkdir -p /config /socket /secrets
RUN useradd _rspamd

USER _rspamd
CMD rspamd -f
