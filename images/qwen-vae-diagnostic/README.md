# Qwen Image 2.1 VAE diagnostic

Version 0.1.0 is a standalone round-trip diagnostic built from
stable-diffusion.cpp `d637cfb935feb2254898a8f1524046c958f3df80` and its pinned
submodules. It constructs only the production VAE runner; no diffusion,
text/vision encoder, sampler, or noise generator is constructed.

The image deliberately derives from the pinned upstream Vulkan runtime instead
of the usual minimal base: identical Mesa and ggml runtime binaries matter for
this comparison. Only the instrumented stable-diffusion library and diagnostic
executable are replaced. Updating either source or runtime requires revalidation
and a new diagnostic version, not an automatic dependency update.

The fixed profile uses `/models/qwen_image_2.1_vae_bf16.safetensors`,
`VERSION_QWEN_IMAGE_2_1`, Vulkan0 on an Arc B580, CPU parameter storage, flash
attention, four threads, the production reference resize to a 1024 x 1024 target
area, and 256 x 256 spatial tiles with 0.5 overlap and zero relative overrides.
Production tensor types, input scaling, latent mean/std conversions, tile
blending, and PNG output functions are reused unchanged. Decode allocation
failure ends the diagnostic; it never retries untiled.

```sh
timeout --signal=TERM --kill-after=10s 600s \
  /sd.cpp/bin/sd-qwen21-vae-roundtrip \
  --input /input/original.png --output-dir /results/new-run
```

The input must be an existing PNG and the output directory must not exist. Its
parent must already exist. Mount input and models read-only, with a separate
writable results mount. The executable refuses inference unless cgroup v2
enforces at most 16 GiB RAM, at most four CPUs, and zero swap. The Kubernetes
workload must separately reserve the complete GPU and wait until other models
have been unloaded. The timeout is a safety budget, not a runtime estimate.

Outputs are `preprocessed.png`, `reconstructed.png`, and `diagnostic.log`.
The log captures stdout/stderr, source/submodule/patch identity, CMake settings,
runtime weight types, effective settings, resolved tiles, and stage timings.
Five float32 checkpoints report shapes, finite-only min/max/mean/population
standard deviation, and separate NaN/positive/negative infinity counts. Invalid
values fail the diagnostic without sanitization. The pre-clamp decode checkpoint
uses an optional const observer immediately before the production output scaling
and clamping; without an observer the production computation is unchanged.

The reference resize calculation is extracted into one shared helper used by
the image pipeline and the diagnostic. The diagnostic still invokes the normal
reference `ImagePreprocessor` byte/float round trip and channel conversion.

`--help`, `--version`, `--build-info`, and `--self-test` load no models and do not
initialize GPU backends. The build runs the self-test for finite/invalid tensor
statistics, native reference preprocessing, and resize rounding.
