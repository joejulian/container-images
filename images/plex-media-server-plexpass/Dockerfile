FROM archlinux:latest as build
LABEL plex-media-server-plexpass package builder

ARG URL=https://aur.archlinux.org/cgit/aur.git/snapshot/plex-media-server-plexpass.tar.gz

RUN pacman -Sy --noconfirm binutils fakeroot file grep gzip tar sudo debugedit
RUN mkdir -p /tmp/build && chmod 777 /tmp/build
USER nobody
RUN curl -L --no-verbose $URL | tar -C /tmp/build -xzv
WORKDIR /tmp/build/plex-media-server-plexpass
RUN makepkg --noconfirm --nocolor --noprogressbar

FROM archlinux:latest

# install the package created from the previously run build container
COPY --from=build /tmp/build/plex-media-server-plexpass/plex-media-server-plexpass*.tar.zst /var/cache/pacman/pkg/
RUN pacman --noconfirm -U /var/cache/pacman/pkg/plex-media-server-plexpass*.tar.zst
RUN pacman --noconfirm -Syu
RUN pacman --noconfirm -S --ignore filesystem --ignore systemd --ignore systemd-sysvcompat --assume-installed systemd-sysvcompat --assume-installed systemd --assume-installed wayland libva sudo && pacman --noconfirm -Sccc && rm -rf /var/cache/pacman

# set up the environment
ENV LD_LIBRARY_PATH=/usr/lib/plexmediaserver/Resources \
    PLEX_MEDIA_SERVER_HOME=/usr/lib/plexmediaserver \
    PLEX_MEDIA_SERVER_MAX_PLUGIN_PROCS=6 \
    PLEX_MEDIA_SERVER_TMPDIR=/tmp \
    TMPDIR=/tmp

# This is a container. Run from script and let the container manager
# manage lifecycle maintenance.
COPY runserver.sh /
USER plex
CMD /runserver.sh
