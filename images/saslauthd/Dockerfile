FROM golang:1.27@sha256:6928d94d1142af58816fed5a62338d605a266ccd53a0deaab6b1096f19059261 AS fsyslog
ENV GOTOOLCHAIN=auto
# renovate: datasource=git-tags depName=gitlab.com/joejulian/fsyslog versioning=semver
ARG FSYSLOG_VERSION=v0.4.0
RUN CGO_ENABLED=0 go install gitlab.com/joejulian/fsyslog@"${FSYSLOG_VERSION}"

FROM debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libsasl2-modules-ldap \
      sasl2-bin && \
    rm -rf /var/lib/apt/lists/*
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD ["fsyslog", "-command", "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"]
