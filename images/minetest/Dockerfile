FROM archlinux:latest

RUN pacman -Syu --noconfirm luanti-server && \
    mkdir -p /usr/games && \
    ln -sf /usr/bin/luantiserver /usr/games/minetest && \
    pacman -Scc --noconfirm
