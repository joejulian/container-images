FROM ghcr.io/joejulian/container-images/node:26.12.1@sha256:33d001c867e40433d6f5fea81e404290601cc498361732f9696178cf7244a370 AS node

FROM ghcr.io/joejulian/container-images/python:3.13.15-bookworm@sha256:e0def53ea821a347b8fd19d51e17ff03032ccca5cacb316fcec3750bc468b1e1

COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN python --version && node --version
