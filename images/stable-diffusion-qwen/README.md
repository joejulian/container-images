# stable-diffusion-qwen

Downstream Vulkan server with persistent browser drafts and the Qwen3-VL IMROPE
temporal-tail correction. Version 0.2.0 rebases both application patches onto
upstream `95ff76230889898e1bf40058ba272a3699b50dc6` and its pinned submodules:

- Web UI: `34e5ad6edcaf827b7fe1e9ffa55ee86cd2fc43d2`.
- ggml: `a5915eb0e47adef21c3f25b889a008925ea838c2`.

## Browser drafts

A persistent, SameSite=Lax cookie identifies the browser's draft. The cookie
contains only an opaque identifier; prompts and images are not sent as cookies.
Prompts, numeric settings, recipe/model-file selections, expanded sections and
the last job ID are saved in localStorage. Image inputs are saved in IndexedDB
so large reference images do not overflow cookie or localStorage quotas.
Drafts are scoped to the application path and configured backend URL.

Reloading restores the form before enabling interaction. Server-info refreshes
and automatic recipe/catalog updates preserve entered values. Choosing a recipe
explicitly still applies its defaults when that option is checked. Reloading a
running job resumes polling its existing ID without submitting another job.
Removing an uploaded image updates the saved draft. Browser storage failures
produce a visible message and leave the form usable. Clearing the site's cookies
or browser storage removes its saved draft.

The headless Chromium regression suite runs during the frontend image build,
with GPU use disabled and all generation/model APIs mocked. It verifies:

- Long prompts, nested settings, large image inputs and expanded sections after
  server-info refresh and page reload.
- Recipe and model-file selections without reapplying recipe defaults.
- Reload while the server is unavailable, followed by reconnect.
- Existing-job recovery and cancellation without another submission.
- Image removal, tab reopening and a full browser restart.
- Visible storage failures with a usable form.

Run it locally against a built frontend with:

```sh
npm ci --prefix images/stable-diffusion-qwen/tests/frontend
node images/stable-diffusion-qwen/tests/frontend/test-draft.mjs /path/to/frontend/dist
```

Set `CHROMIUM_PATH` for a different Chromium executable. Set `APP_URL` to test an
already-served frontend; API calls remain mocked and no inference runs. Optional
`SCREENSHOT_DIR` writes desktop and mobile screenshots outside the source tree.

## Qwen encoder correction

The patch copies final temporal positions to the fourth position axis after
image-grid adjustments. This supplies temporal positions used by the last two
rotary-frequency pairs. Explicit position IDs and other encoder architectures
retain their upstream behavior. The regression test compiles the actual
production position-building block, including upstream's expanded image tokens,
and checks text-only, square/rectangular and multiple references plus explicit
position-ID overrides. The build verifies that the unpatched block fails the
corrected-position assertions, then that the patched block passes.

This correction changes conditioning numerically; it does not resolve Qwen 2.1's
reference noise-replay behavior. Use an edit seed different from the seed that
generated the reference, or a fresh random seed (`--seed -1`).

## Build and release

The source and upstream runtime digest are a matched pair. Rebuild the shared
application library and server to embed the patched UI; keep ggml backends and
Mesa from the runtime built at the same source revision. Final-image checks
verify dynamic linkage and server argument parsing without loading models or
accessing a GPU. The startup wrapper announces the downstream features.

`/opt/sd-patch/build-provenance.txt` records the source, pinned submodules, patches,
frontend header, executable/library checksums and CMake configuration. `VERSION`
identifies the downstream application release. Publish an image-scoped tag such
as `stable-diffusion-qwen/v0.2.0` through the repository release workflow.
Arguments, model paths, generation defaults and resource budgets remain the
caller's responsibility.

Advance source/runtime/submodules together with a new downstream version and
regression validation. Renovate excludes this matched pair from independent
base-image updates. Deploy the downstream repository and an immutable
version/digest so upstream upgrades cannot silently remove the patches.
