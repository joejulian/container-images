"""Compare production VAE tiles with the unmodified, pinned upstream VAE.

Only checkpoint names and singleton convolution dimensions are adapted. No
encoder calculations, production tensors, or non-finite values are changed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import torch
from diffusers.models.autoencoders.autoencoder_kl_qwenimage21 import AutoencoderKLQwenImage21
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parent
WEIGHTS = Path("/models/qwen_image_2.1_vae_bf16.safetensors")
DIFFUSERS_SHA = "6256aa7666cedd47443adc8f82da9a10e110b09c"
CONFIG_SHA = "d26bb61231c349cf6b7896fa83353113880e1ba3"


def renamed(key):
    # Qwen 2.1 uses nested residual down/up blocks, unlike the older Wan
    # single-file converter. These names follow the pinned class hierarchy.
    key = re.sub(r"^conv1\.", "quant_conv.", key)
    key = re.sub(r"^conv2\.", "post_quant_conv.", key)
    key = re.sub(r"^(encoder|decoder)\.conv1\.", r"\1.conv_in.", key)
    key = re.sub(r"\.middle\.0\.", ".mid_block.resnets.0.", key)
    key = re.sub(r"\.middle\.2\.", ".mid_block.resnets.1.", key)
    key = re.sub(r"\.middle\.1\.", ".mid_block.attentions.0.", key)
    key = key.replace(".head.0.", ".norm_out.").replace(".head.2.", ".conv_out.")
    key = re.sub(r"encoder\.downsamples\.(\d+)\.downsamples\.([01])\.",
                 r"encoder.down_blocks.\1.resnets.\2.", key)
    key = re.sub(r"encoder\.downsamples\.(\d+)\.downsamples\.2\.",
                 r"encoder.down_blocks.\1.downsampler.", key)
    key = re.sub(r"decoder\.upsamples\.(\d+)\.upsamples\.([012])\.",
                 r"decoder.up_blocks.\1.resnets.\2.", key)
    key = re.sub(r"decoder\.upsamples\.(\d+)\.upsamples\.3\.",
                 r"decoder.up_blocks.\1.upsampler.", key)
    for old, new in (("residual.0", "norm1"), ("residual.2", "conv1"),
                     ("residual.3", "norm2"), ("residual.6", "conv2"),
                     ("shortcut", "conv_shortcut")):
        key = key.replace(f".{old}.", f".{new}.")
    return key


def convert_weights(original, expected):
    converted, mapping = {}, []
    for old, value in original.items():
        key = renamed(old)
        if key not in expected or key in converted:
            raise ValueError(f"unknown or duplicate tensor: {old} -> {key}")
        target = expected[key]
        before = list(value.shape)
        squeezed = False
        if value.ndim == 5 and value.shape[2] == 1 and target.ndim == 4:
            value = value.squeeze(2)
            squeezed = True
        if value.shape != target.shape:
            raise ValueError(f"shape mismatch {old}: {value.shape} != {target.shape}")
        converted[key] = value.to(dtype=torch.float32)
        mapping.append(dict(source=old, target=key, source_shape=before,
                            target_shape=list(value.shape), squeeze_temporal_axis=squeezed))
    if converted.keys() != expected.keys():
        raise ValueError(f"missing tensors: {sorted(expected.keys() - converted.keys())}")
    return converted, mapping


def read_tensor(stem):
    meta = json.loads(stem.with_suffix(".json").read_text())
    if meta["dtype"] != "<f4" or meta["layout"] != "ggml_first_axis_contiguous":
        raise ValueError("unsupported tensor storage")
    a = np.fromfile(stem.with_suffix(".f32"), dtype="<f4")
    a = a.reshape(meta["shape"][::-1])
    if a.ndim != 4:
        raise ValueError(f"expected WHCB, got {meta['shape']}")
    return a[:, :, None, :, :]  # NCHW -> NCTHW; no normalization here.


def stats(a):
    a = np.asarray(a)
    finite = a[np.isfinite(a)].astype(np.float64)
    return dict(shape=list(a.shape), dtype=str(a.dtype),
                nan=int(np.isnan(a).sum()), inf=int(np.isinf(a).sum()),
                minimum=float(finite.min()) if finite.size else None,
                maximum=float(finite.max()) if finite.size else None,
                mean=float(finite.mean()) if finite.size else None,
                std=float(finite.std()) if finite.size else None)


def compare(actual, reference):
    if actual.shape != reference.shape:
        raise ValueError(f"comparison shape mismatch: {actual.shape} != {reference.shape}")
    result = dict(actual=stats(actual), reference=stats(reference))
    if not np.isfinite(actual).all() or not np.isfinite(reference).all():
        result["valid"] = False
        return result
    a, b = actual.astype(np.float64), reference.astype(np.float64)
    delta = a - b
    rms = float(np.sqrt(np.mean(b * b)))
    rmse = float(np.sqrt(np.mean(delta * delta)))
    norms = float(np.linalg.norm(a) * np.linalg.norm(b))
    result.update(valid=True, mae=float(np.abs(delta).mean()), rmse=rmse,
                  max_abs=float(np.abs(delta).max()), relative_rmse=rmse / rms if rms else None,
                  cosine=float(np.sum(a * b) / norms) if norms else None,
                  per_channel_rmse=np.sqrt(np.mean(delta * delta, axis=(0, 2, 3, 4))).tolist())
    return result


def limits():
    root = Path("/sys/fs/cgroup")
    memory, swap, cpu = [(root / x).read_text().strip() for x in
                         ("memory.max", "memory.swap.max", "cpu.max")]
    quota, period = cpu.split()
    if memory == "max" or int(memory) > 16 * 1024**3 or swap != "0":
        raise ValueError("requires <=16 GiB memory and zero swap")
    if quota == "max" or int(quota) / int(period) > 4:
        raise ValueError("requires <=4 CPUs")
    return dict(memory_max=memory, swap_max=swap, cpu_max=cpu)


def reference_run(output, tile_ids):
    started = time.monotonic()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    config = json.loads((ROOT / "vae-config.json").read_text())
    report = dict(diffusers_sha=DIFFUSERS_SHA, config_sha=CONFIG_SHA,
                  torch=torch.__version__, reference_device="cpu", reference_dtype="float32",
                  production_device="Vulkan0", production_precision="unchanged production mix",
                  cgroup=limits(), tile_pixels=[256, 256], production_overlap=0.5,
                  comparison="identical production tiles before blending", tiles=[])
    def record():
        (output / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    record()
    # Meta construction allocates no randomly initialized parameters. Strict
    # loading replaces every parameter with the existing checkpoint values.
    with torch.device("meta"):
        vae = AutoencoderKLQwenImage21.from_config(config)
    original = load_file(str(WEIGHTS), device="cpu")
    report["stored_dtypes"] = sorted({str(x.dtype) for x in original.values()})
    converted, mapping = convert_weights(original, vae.state_dict())
    vae.load_state_dict(converted, strict=True, assign=True)
    del original, converted
    vae.eval()
    vae.enable_tiling(tile_sample_min_height=256, tile_sample_min_width=256,
                     tile_sample_stride_height=128, tile_sample_stride_width=128)
    (output / "weight-mapping.json").write_text(json.dumps(mapping, indent=2) + "\n")
    with WEIGHTS.open("rb") as stream:
        report["weights_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    report["loaded_components"] = ["VAE"]
    report["mapped_tensors"] = len(mapping)
    report["load_seconds"] = time.monotonic() - started
    mean = np.asarray(config["latents_mean"], dtype=np.float32)[None, :, None, None, None]
    std = np.asarray(config["latents_std"], dtype=np.float32)[None, :, None, None, None]
    report["assembled_normalization"] = compare(read_tensor(output / "reference-normalized"),
                                                 (read_tensor(output / "encoder-raw") - mean) / std)
    record()
    for tile_id in tile_ids:
        start = time.monotonic()
        stem = output / "tiles" / str(tile_id)
        x = read_tensor(Path(str(stem) + "-input"))
        raw = read_tensor(Path(str(stem) + "-raw"))
        normalized = read_tensor(Path(str(stem) + "-normalized"))
        if x.shape != (1, 4, 1, 256, 256):
            raise ValueError("only exported 256x256 production tiles are allowed")
        print(f"reference tile={tile_id} input={stats(x)}", flush=True)
        with torch.inference_mode():
            # mode(), never sample(): no RNG and no added noise.
            oracle = vae.encode(torch.from_numpy(x)).latent_dist.mode().numpy()
        np.save(str(stem) + "-upstream-raw.npy", oracle)
        oracle_normalized = (oracle - mean) / std
        np.save(str(stem) + "-upstream-normalized.npy", oracle_normalized)
        item = dict(tile_id=tile_id, seconds=time.monotonic() - start,
                    raw=compare(raw, oracle), normalized=compare(normalized, oracle_normalized))
        report["tiles"].append(item)
        report["reference_seconds"] = time.monotonic() - started
        record()
        print(json.dumps(item, allow_nan=False), flush=True)
        if not item["raw"]["valid"] or not item["normalized"]["valid"]:
            raise ValueError("non-finite values retained; stopping comparison")
    report["result"] = "success"
    report["limitations"] = ["CPU float32 oracle versus production Vulkan mixed precision",
                              "selected tiles only; no claim of full-image tiled parity",
                              "native tile blending algorithms differ and are not compared"]
    record()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tiles", default="24,0,48", help="production row-major tile indices")
    args = parser.parse_args()
    tile_ids = [int(x) for x in args.tiles.split(",")]
    if not tile_ids or any(x < 0 for x in tile_ids) or len(set(tile_ids)) != len(tile_ids):
        parser.error("tile indices must be nonnegative and unique")
    limits()
    subprocess.run(["/sd.cpp/bin/sd-qwen21-vae-roundtrip", "--input", str(args.input),
                    "--output-dir", str(args.output_dir), "--export-latents"], check=True)
    with (args.output_dir / "reference.log").open("x", buffering=1) as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())
        reference_run(args.output_dir, tile_ids)


if __name__ == "__main__":
    main()
