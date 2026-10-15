# stable-diffusion-qwen

Downstream Vulkan server build with the Qwen3-VL IMROPE temporal-tail correction.
The patch copies the final temporal positions to the fourth position axis after
image-grid adjustments. This supplies the temporal positions used by the last
two rotary-frequency pairs. Other encoder architectures retain their behavior.

The image replaces only `libstable-diffusion.so` in the matching upstream runtime.
It keeps the server executable, embedded web UI, ggml backends, and Mesa libraries.
There is no diagnostic flag: the correction is always enabled for Qwen3-VL.
The `/sd-server` wrapper announces the patch at startup. Arguments, model paths,
resource budgets, and generation defaults remain the caller's responsibility.

Upstream source: `e47426c04460827e698b6f88ec6431a2007d5c27`.
Pinned ggml: `d25b121ce1d6ae0c7e62ad080460d9fc1e46dd93`.
`/opt/sd-patch/build-provenance.txt` records the source, submodules, patch checksum,
library checksum, and CMake configuration. `VERSION` identifies the downstream
application release, not an upstream semver release. Publish using an image-scoped
tag such as `stable-diffusion-qwen/v0.1.0` through the repository release workflow.

The runtime digest and source revision must advance together, with a new
downstream version and regression validation. Renovate excludes this matched pair
from independent base-image updates. Deploy the downstream repository and an
immutable version/digest so upstream updates cannot silently remove the patch.

The model-free regression test compiles the actual production position-building
block extracted from `LLMRunner::build_graph`. It checks text-only inputs, square
and rectangular references, multiple references, and unaffected encoder paths.
The build verifies that the original block fails the corrected-position assertions,
then that the patched block passes. Final-image checks verify dynamic linkage and
server argument parsing without loading a model or accessing a GPU.

Earlier encoder diagnostics established a conditioning change. This release does
not establish that the correction fixes visible image texture corruption; that
still requires comparing generated images.
