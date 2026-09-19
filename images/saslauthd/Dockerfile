FROM golang:1.27@sha256:03fd17ca31f26e3c8d5b83ae0606044133c59e0788784dd6f371da59cdb3b46f AS fsyslog
ENV GOTOOLCHAIN=auto
# renovate: datasource=git-tags depName=gitlab.com/joejulian/fsyslog versioning=semver
ARG FSYSLOG_VERSION=v0.4.0
RUN CGO_ENABLED=0 go install gitlab.com/joejulian/fsyslog@"${FSYSLOG_VERSION}"

FROM debian:trixie-slim@sha256:e27e3dbef3b2064bed82f2fef343c0d02a4b8d5675e5b2c511883442e001630d

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libsasl2-modules-ldap \
      sasl2-bin && \
    rm -rf /var/lib/apt/lists/*
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD ["fsyslog", "-command", "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"]
