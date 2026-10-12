FROM ghcr.io/leejet/stable-diffusion.cpp:master-vulkan@sha256:cc4162fbb7161827ee7417a518c836e9ea4930c6cfc1b40b961c845a2cae73da AS serving-runtime

FROM serving-runtime AS build
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git cmake libvulkan-dev glslc spirv-headers ca-certificates
WORKDIR /source
ARG SD_REVISION=d637cfb935feb2254898a8f1524046c958f3df80
RUN git init && git remote add origin https://github.com/leejet/stable-diffusion.cpp.git && \
    git fetch --depth=1 origin "$SD_REVISION" && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "$SD_REVISION" && \
    git submodule update --init --recursive --depth=1
COPY source.patch /diagnostic/source.patch
RUN git apply --unidiff-zero --check /diagnostic/source.patch && git apply --unidiff-zero /diagnostic/source.patch
COPY main.cpp CMakeLists.txt /source/examples/vae-diagnostic/
COPY reference_image.h /source/src/pipeline/reference_image.h
RUN cmake -S /source -B /build \
    -DSD_BUILD_EXAMPLES=OFF -DSD_BUILD_VAE_DIAGNOSTIC=ON \
    -DSD_VULKAN=ON -DSD_BUILD_SHARED_LIBS=ON -DGGML_NATIVE=OFF \
    -DSD_BUILD_SHARED_GGML_LIB=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DCMAKE_INSTALL_RPATH='$ORIGIN' && \
    cmake --build /build --target sd-qwen21-vae-roundtrip --parallel 2
RUN mkdir -p /diagnostic && \
    { printf '%s\n' 'runtime_image=ghcr.io/leejet/stable-diffusion.cpp@sha256:cc4162fbb7161827ee7417a518c836e9ea4930c6cfc1b40b961c845a2cae73da'; \
      git rev-parse HEAD; git submodule status --recursive; \
      sha256sum /diagnostic/source.patch examples/vae-diagnostic/main.cpp \
        examples/vae-diagnostic/CMakeLists.txt src/pipeline/reference_image.h; \
      cat /build/CMakeCache.txt; \
    } > /diagnostic/build-provenance.txt

FROM serving-runtime
# Keep the production ggml backend binaries and Mesa libraries unchanged.
COPY --from=build /build/bin/sd-qwen21-vae-roundtrip /build/bin/libstable-diffusion.so /sd.cpp/bin/
COPY --from=build /diagnostic/build-provenance.txt /opt/vae-diagnostic/build-provenance.txt
RUN /sd.cpp/bin/sd-qwen21-vae-roundtrip --self-test
WORKDIR /sd.cpp
ENTRYPOINT []
CMD ["/sd.cpp/bin/sd-qwen21-vae-roundtrip", "--help"]
