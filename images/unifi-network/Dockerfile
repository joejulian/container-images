FROM ghcr.io/linuxserver/unifi-network-application:10.6.109@sha256:8389f585c6443af7051b4696a09e4bb5408636da7f99c5a0e5a883595c1d434c

# The upstream application and JRE are maintained by LinuxServer. Start Java
# directly so this image needs neither root nor the s6 initialization layer.
RUN ln -s /unifi/data /usr/lib/unifi/data \
    && ln -s /unifi/logs /usr/lib/unifi/logs \
    && ln -s /unifi/run /usr/lib/unifi/run
COPY --chmod=755 entrypoint.sh /usr/local/bin/unifi-network
COPY --chmod=755 version.sh /usr/local/bin/unifi-network-version
USER 999:999
WORKDIR /unifi
ENTRYPOINT ["/usr/local/bin/unifi-network"]
CMD []
