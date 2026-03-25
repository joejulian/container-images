FROM golang:1.24 as fsyslog
RUN go install gitlab.com/joejulian/fsyslog@v0.3.1

FROM archlinux:latest

RUN pacman -Syu --noconfirm cyrus-sasl && pacman -Scc --noconfirm && rm -rf /var/cache/pacman/pkg
COPY --from=fsyslog /go/bin/fsyslog /bin/fsyslog

CMD fsyslog -command "saslauthd -d -a ldap -O /config/saslauthd.conf -m /socket"
