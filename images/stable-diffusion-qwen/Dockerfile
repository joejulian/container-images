# Runtime/source/submodules are a matched pair; advance them together and bump VERSION.
FROM ghcr.io/leejet/stable-diffusion.cpp:master-vulkan@sha256:0b496044f2f9970c41042180f87163d216f24c744347c3781e35276d4b581307 AS serving-runtime

FROM serving-runtime AS source
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git cmake libvulkan-dev glslc spirv-headers ca-certificates python3
WORKDIR /source
ARG SD_REVISION=95ff76230889898e1bf40058ba272a3699b50dc6
RUN git init && git remote add origin https://github.com/leejet/stable-diffusion.cpp.git && \
    git fetch --depth=1 origin "$SD_REVISION" && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "$SD_REVISION" && \
    git submodule update --init --recursive --depth=1
COPY source.patch test_positions.py /patch/
RUN python3 /patch/test_positions.py --expect-original /source && \
    git apply --check /patch/source.patch && git apply /patch/source.patch && \
    python3 /patch/test_positions.py /source

FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS frontend
RUN apk add --no-cache git chromium && npm install --global pnpm@10.15.1
COPY tests/frontend/ /tests/
RUN npm --prefix /tests ci
WORKDIR /frontend
COPY --from=source /source/examples/server/frontend/ ./
COPY frontend.patch /patch/frontend.patch
RUN rm .git && git init && git apply --check /patch/frontend.patch && git apply /patch/frontend.patch && \
    pnpm install --frozen-lockfile && pnpm run type-check && \
    pnpm run build && pnpm run build:header && \
    node /tests/test-draft.mjs /frontend/dist

FROM source AS build
COPY --from=frontend /frontend/dist/ /source/examples/server/frontend/dist/
RUN cmake -S /source -B /build \
    -DSD_BUILD_EXAMPLES=ON -DSD_VULKAN=ON -DSD_BUILD_SHARED_LIBS=ON \
    -DGGML_NATIVE=OFF -DSD_BUILD_SHARED_GGML_LIB=ON \
    -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DCMAKE_INSTALL_RPATH='$ORIGIN' && \
    cmake --build /build --target sd-server --parallel 2
COPY frontend.patch /patch/
RUN { git rev-parse HEAD; git submodule status --recursive; \
      sha256sum /patch/source.patch /patch/frontend.patch /patch/test_positions.py \
        /source/examples/server/frontend/dist/gen_index_html.h \
        /build/bin/libstable-diffusion.so /build/bin/sd-server; \
      cat /build/CMakeCache.txt; \
    } > /patch/build-provenance.txt

FROM serving-runtime
# Rebuild the server to embed the patched UI. ggml and Mesa remain from the
# runtime built from the exact same source revision and pinned submodules.
COPY --from=build /build/bin/libstable-diffusion.so /build/bin/sd-server /sd.cpp/bin/
COPY --from=build /patch/build-provenance.txt /opt/sd-patch/build-provenance.txt
COPY source.patch frontend.patch VERSION /opt/sd-patch/
COPY --chmod=755 sd-server /sd-server
RUN { ldd -r /sd.cpp/bin/libstable-diffusion.so; ldd -r /sd.cpp/bin/sd-server; } > /opt/sd-patch/linkage.txt 2>&1 && \
    ! grep -E 'not found|undefined symbol' /opt/sd-patch/linkage.txt && \
    /sd-server --help > /opt/sd-patch/server-help.txt 2>&1 && \
    grep -q 'browser draft persistence enabled' /opt/sd-patch/server-help.txt
LABEL io.stable-diffusion.upstream-revision="95ff76230889898e1bf40058ba272a3699b50dc6" \
      io.stable-diffusion.frontend-revision="34e5ad6edcaf827b7fe1e9ffa55ee86cd2fc43d2" \
      io.stable-diffusion.patch="qwen3-vl-imrope-temporal-tail-v1,webui-draft-v1"
WORKDIR /sd.cpp
ENTRYPOINT []
CMD ["/sd-server", "--help"]
