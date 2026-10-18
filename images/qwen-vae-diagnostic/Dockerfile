FROM ghcr.io/leejet/stable-diffusion.cpp:master-vulkan@sha256:b37874d61e8ce1917be27b0201f95dce261b4f4f35a92e8dfaabd65f0f22f993 AS serving-runtime

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
COPY main.cpp conditioning.cpp diagnostic_common.h CMakeLists.txt /source/examples/vae-diagnostic/
COPY reference_image.h /source/src/pipeline/reference_image.h
RUN cmake -S /source -B /build \
    -DSD_BUILD_EXAMPLES=OFF -DSD_BUILD_VAE_DIAGNOSTIC=ON \
    -DSD_VULKAN=ON -DSD_BUILD_SHARED_LIBS=ON -DGGML_NATIVE=OFF \
    -DSD_BUILD_SHARED_GGML_LIB=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DCMAKE_INSTALL_RPATH='$ORIGIN' && \
    cmake --build /build --target sd-qwen21-vae-roundtrip sd-qwen21-conditioning --parallel 2
RUN mkdir -p /diagnostic && \
    { printf '%s\n' 'runtime_image=ghcr.io/leejet/stable-diffusion.cpp@sha256:cc4162fbb7161827ee7417a518c836e9ea4930c6cfc1b40b961c845a2cae73da'; \
      git rev-parse HEAD; git submodule status --recursive; \
      sha256sum /diagnostic/source.patch examples/vae-diagnostic/main.cpp \
        examples/vae-diagnostic/CMakeLists.txt examples/vae-diagnostic/conditioning.cpp \
        examples/vae-diagnostic/diagnostic_common.h src/pipeline/reference_image.h; \
      cat /build/CMakeCache.txt; \
    } > /diagnostic/build-provenance.txt

FROM serving-runtime AS reference-runtime
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv git ca-certificates
RUN python3 -m venv /opt/vae-reference
# These reference pins are part of the experiment identity; update deliberately.
ARG TORCH_VERSION=2.9.0+cpu
ARG DIFFUSERS_REVISION=6256aa7666cedd47443adc8f82da9a10e110b09c
RUN /opt/vae-reference/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==$TORCH_VERSION"
RUN /opt/vae-reference/bin/pip install --no-cache-dir numpy==2.2.6 safetensors==0.8.0 \
      "diffusers @ git+https://github.com/huggingface/diffusers.git@$DIFFUSERS_REVISION" && \
    /opt/vae-reference/bin/pip freeze > /opt/vae-reference/requirements-frozen.txt

FROM reference-runtime
# Keep the production ggml backend binaries and Mesa libraries unchanged.
COPY --from=build /build/bin/sd-qwen21-vae-roundtrip /build/bin/sd-qwen21-conditioning /build/bin/libstable-diffusion.so /sd.cpp/bin/
COPY --from=build /diagnostic/build-provenance.txt /opt/vae-diagnostic/build-provenance.txt
COPY latent_parity.py test_latent_parity.py conditioning_ab.py test_conditioning_ab.py vae-config.json /opt/vae-diagnostic/
RUN /sd.cpp/bin/sd-qwen21-vae-roundtrip --self-test && \
    cd /opt/vae-diagnostic && /opt/vae-reference/bin/python -m unittest -v test_latent_parity test_conditioning_ab && \
    cat /opt/vae-reference/requirements-frozen.txt >> build-provenance.txt && \
    sha256sum latent_parity.py conditioning_ab.py vae-config.json >> build-provenance.txt
ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
WORKDIR /sd.cpp
ENTRYPOINT []
CMD ["/sd.cpp/bin/sd-qwen21-vae-roundtrip", "--help"]
