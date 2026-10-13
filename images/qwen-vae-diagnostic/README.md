# Qwen Image 2.1 VAE diagnostic

Version 0.2.0 is a standalone round-trip and latent comparison diagnostic built from
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

## Latent comparison

```sh
timeout --signal=TERM --kill-after=10s 600s \
  /opt/vae-reference/bin/python /opt/vae-diagnostic/latent_parity.py \
  --input /input/original.png --output-dir /results/new-comparison
```

The wrapper first runs the production executable with `--export-latents`, which
skips decoding and saves all actual encoder tile inputs, raw outputs, normalized
outputs, and assembled latents as little-endian float32 with shape metadata.
Its optional const tile observer runs before production blending. The production
process then exits before the independent reference loads the same local weights.

The oracle is the unmodified Diffusers `AutoencoderKLQwenImage21` at
`6256aa7666cedd47443adc8f82da9a10e110b09c`. Its config is copied from
`Qwen/Qwen-Image-2.1` revision `d26bb61231c349cf6b7896fa83353113880e1ba3`,
`vae/config.json`. The adapter renames original checkpoint keys according to the
Qwen 2.1 residual block hierarchy, removes only singleton temporal convolution
axes where the destination requires it, and requires every name and shape to
match. It writes the complete mapping and checkpoint SHA256 to the results.

Reference arithmetic is **CPU float32**, promoting the existing BF16 values
without replacing weights. Production Vulkan arithmetic remains unchanged.
The VAE is the only constructed model. Reference encoding uses `.mode()`, never
sampling. Tiling remains enabled at 256 pixels with stride 128; reference inputs
are already individual production tiles. No full image is encoded untiled.

The default compares production tile indices 24, 0, and 48 (center and opposite
corners for the fixed 1024-square profile). `--tiles` accepts an explicit comma
separated selection. The exported floats supply the exact input range; there is
no second image normalization. Outputs include `reference.log`, `comparison.json`,
`weight-mapping.json`, and reference tile NumPy arrays. Results are written after
each tile, so a timeout retains completed comparisons. Metrics include raw and
normalized RMSE, relative RMSE, maximum error, cosine similarity, and per-channel
RMSE. Assembled production normalization is separately checked against the
official mean/std constants. Non-finite values are retained and fail the test.

This compares selected tiles **before blending**, not full-image parity:
production and Diffusers use different tile placement and blending. Device and
arithmetic precision also differ, so small numerical differences are expected;
the tool reports measurements rather than an arbitrary parity pass threshold.
The model-free Python tests validate export layout, comparison statistics,
invalid-value handling, and strict key/shape adaptation on the meta device.
