FROM archlinux:latest

RUN pacman -Sy nzbget unrar p7zip --noconfirm && \
    pacman -Scc --noconfirm

EXPOSE 6789
VOLUME /mnt/media
VOLUME /mnt/config

USER nobody
CMD [ "nzbget", "-s", "-c", "/mnt/config/nzbget.conf" ]
