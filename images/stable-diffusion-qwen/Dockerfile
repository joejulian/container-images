# Runtime and source revision are a matched pair; update them together and bump VERSION.
FROM ghcr.io/leejet/stable-diffusion.cpp:master-vulkan@sha256:84a58175bb8c20314bd1385e2c41a0c1edd767523d25d3e068700de0cc3f5560 AS serving-runtime

FROM serving-runtime AS build
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git cmake libvulkan-dev glslc spirv-headers ca-certificates python3
WORKDIR /source
ARG SD_REVISION=e47426c04460827e698b6f88ec6431a2007d5c27
RUN git init && git remote add origin https://github.com/leejet/stable-diffusion.cpp.git && \
    git fetch --depth=1 origin "$SD_REVISION" && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "$SD_REVISION" && \
    git submodule update --init --recursive --depth=1
COPY source.patch test_positions.py /patch/
# Exercise the production position-building block without loading models or a GPU.
RUN python3 /patch/test_positions.py --expect-original /source && \
    git apply --check /patch/source.patch && git apply /patch/source.patch && \
    python3 /patch/test_positions.py /source
RUN cmake -S /source -B /build \
    -DSD_BUILD_EXAMPLES=OFF -DSD_VULKAN=ON -DSD_BUILD_SHARED_LIBS=ON \
    -DGGML_NATIVE=OFF -DSD_BUILD_SHARED_GGML_LIB=ON \
    -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DCMAKE_INSTALL_RPATH='$ORIGIN' && \
    cmake --build /build --target stable-diffusion --parallel 2
RUN { git rev-parse HEAD; git submodule status --recursive; \
      sha256sum /patch/source.patch /patch/test_positions.py /build/bin/libstable-diffusion.so; \
      cat /build/CMakeCache.txt; \
    } > /patch/build-provenance.txt

FROM serving-runtime
# Only the shared application library changes. Keep the matching server, embedded
# frontend, ggml backend binaries, and Mesa runtime from the pinned upstream image.
COPY --from=build /build/bin/libstable-diffusion.so /sd.cpp/bin/libstable-diffusion.so
COPY --from=build /patch/build-provenance.txt /opt/sd-patch/build-provenance.txt
COPY source.patch VERSION /opt/sd-patch/
COPY --chmod=755 sd-server /sd-server
RUN ldd -r /sd.cpp/bin/libstable-diffusion.so > /opt/sd-patch/linkage.txt 2>&1 && \
    ! grep -E 'not found|undefined symbol' /opt/sd-patch/linkage.txt && \
    /sd-server --help > /opt/sd-patch/server-help.txt 2>&1 && \
    grep -q 'Qwen3-VL IMROPE temporal-tail correction enabled' /opt/sd-patch/server-help.txt
LABEL io.stable-diffusion.upstream-revision="e47426c04460827e698b6f88ec6431a2007d5c27" \
      io.stable-diffusion.patch="qwen3-vl-imrope-temporal-tail-v1"
WORKDIR /sd.cpp
ENTRYPOINT []
CMD ["/sd-server", "--help"]
