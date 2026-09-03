# renovate: datasource=github-tags depName=joejulian/unifi-cam-proxy versioning=semver
ARG UNIFI_CAM_PROXY_REF=v0.3.6

FROM python:3.12-alpine3.21 AS builder
WORKDIR /app
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ARG UNIFI_CAM_PROXY_REF

RUN apk add --update \
        cargo \
        git \
        gcc \
        g++ \
        jpeg-dev \
        libc-dev \
        linux-headers \
        musl-dev \
        patchelf \
        rust \
        zlib-dev

RUN pip install -U pip wheel setuptools maturin
RUN git clone --depth 1 --branch "${UNIFI_CAM_PROXY_REF}" \
        https://github.com/joejulian/unifi-cam-proxy.git \
        /src/unifi-cam-proxy
RUN pip install -r /src/unifi-cam-proxy/requirements.txt --no-build-isolation


FROM python:3.12-alpine3.21
WORKDIR /app

COPY --from=builder /usr/local/lib/ /usr/local/lib/

RUN apk add --update ffmpeg netcat-openbsd libusb-dev

COPY --from=builder /src/unifi-cam-proxy/ .
RUN pip install . --no-cache-dir

COPY --from=builder /src/unifi-cam-proxy/docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["unifi-cam-proxy"]
