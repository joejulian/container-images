FROM alpine:edge

RUN apk add --no-cache grep postfix postfix-ldap postfix-pcre postfix-pgsql postfix-sqlite sed

CMD ["postfix", "-c", "/config", "start-fg"]
