FROM archlinux:latest
RUN pacman -Syu --noconfirm python rspamd && pacman -Scc --noconfirm && rm -rf /var/cache/pacman/pkg/*
RUN useradd _rspamd
USER _rspamd
WORKDIR /spamscan
COPY spamscan.py .
CMD python spamscan.py
