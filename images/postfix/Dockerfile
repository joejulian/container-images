FROM alpine:edge@sha256:020dfcbaaf4cc1078bf2d9c7ba31a8466e334061dcd2f248001d68f79e52c000

RUN apk add --no-cache grep postfix postfix-ldap postfix-pcre postfix-pgsql postfix-sqlite sed

CMD ["postfix", "-c", "/config", "start-fg"]
