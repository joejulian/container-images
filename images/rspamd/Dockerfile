FROM alpine:edge

RUN apk add --no-cache rspamd && \
    mkdir -p /config /socket /secrets

USER rspamd
CMD ["rspamd", "-f"]
