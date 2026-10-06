FROM golang:1.27@sha256:162be5298a40ed317005c8339c6de4d10d3eef336d66dc8e9259b03ab9d3a6d2 AS fsyslog
ENV GOTOOLCHAIN=auto
# renovate: datasource=git-tags depName=gitlab.com/joejulian/fsyslog versioning=semver
ARG FSYSLOG_VERSION=v0.4.0
RUN CGO_ENABLED=0 go install gitlab.com/joejulian/fsyslog@"${FSYSLOG_VERSION}"

FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libsasl2-modules-ldap \
      sasl2-bin && \
    rm -rf /var/lib/apt/lists/*
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD ["fsyslog", "-command", "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"]
