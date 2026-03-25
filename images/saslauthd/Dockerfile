FROM golang:1.24 AS fsyslog
ENV GOTOOLCHAIN=auto
RUN go install gitlab.com/joejulian/fsyslog@v0.3.1

FROM alpine:edge

RUN apk add --no-cache cyrus-sasl
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD ["fsyslog", "-command", "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"]
