FROM golang:1.27@sha256:1cfcdb11f37fce9429f617100f39e0251748bbaba454bd431275155701765058 AS fsyslog
ENV GOTOOLCHAIN=auto
# renovate: datasource=git-tags depName=gitlab.com/joejulian/fsyslog versioning=semver
ARG FSYSLOG_VERSION=v0.4.0
RUN CGO_ENABLED=0 go install gitlab.com/joejulian/fsyslog@"${FSYSLOG_VERSION}"

FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libsasl2-modules-ldap \
      sasl2-bin && \
    rm -rf /var/lib/apt/lists/*
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD ["fsyslog", "-command", "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"]
