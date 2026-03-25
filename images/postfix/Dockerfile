FROM archlinux:latest

RUN pacman -Syu --noconfirm --needed grep postfix postfix-ldap postfix-cdb postfix-lmdb postfix-mysql postfix-pcre postfix-pgsql postfix-sqlite sed && pacman -Scc --noconfirm

CMD ["postfix", "-c", "/config", "start-fg"]
