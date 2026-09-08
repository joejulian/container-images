FROM ghcr.io/joejulian/container-images/node:22.23.2@sha256:c1f90c812cd7aa524c82fa213f020ef45628fda5067684c0204f34bfce568bb1 AS node

FROM ghcr.io/joejulian/container-images/python:3.13.15-bookworm@sha256:e0def53ea821a347b8fd19d51e17ff03032ccca5cacb316fcec3750bc468b1e1

COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN python --version && node --version
