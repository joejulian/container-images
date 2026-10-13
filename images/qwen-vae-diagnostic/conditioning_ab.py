"""Measure a Qwen3-VL position correction with independent native processes.

No model implementation is substituted. The native executable constructs only
the installed text/vision architecture, retaining its original weight types.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np


def read_tensor(stem):
    meta = json.loads(stem.with_suffix(".json").read_text())
    if meta["dtype"] != "<f4" or meta["layout"] != "ggml_first_axis_contiguous":
        raise ValueError("unsupported export layout")
    return np.fromfile(stem.with_suffix(".f32"), dtype="<f4").reshape(meta["shape"][::-1])


def compare(reference, candidate):
    if reference.shape != candidate.shape or not reference.size:
        raise ValueError("empty or mismatched tensors")
    if not np.isfinite(reference).all() or not np.isfinite(candidate).all():
        raise ValueError("non-finite checkpoint; raw values retained in exports")
    a, b = reference.astype(np.float64), candidate.astype(np.float64)
    d = b - a
    rms = float(np.sqrt(np.mean(a * a)))
    rmse = float(np.sqrt(np.mean(d * d)))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    result = dict(shape=list(a.shape), reference_rms=rms, rmse=rmse,
                  relative_rmse=rmse / rms if rms else None,
                  mae=float(np.abs(d).mean()), max_abs=float(np.abs(d).max()),
                  cosine=float(np.sum(a * b) / norm) if norm else None,
                  byte_identical=reference.tobytes() == candidate.tobytes(),
                  changed_elements=int(np.count_nonzero(reference != candidate)))
    if a.ndim == 2:
        token_rms = np.sqrt(np.mean(a * a, axis=1))
        delta_rms = np.sqrt(np.mean(d * d, axis=1))
        nonzero = token_rms > 0
        result["token_relative_rmse_quantiles_p0_p50_p95_p99_p100"] = (
            np.quantile(delta_rms[nonzero] / token_rms[nonzero], [0, .5, .95, .99, 1]).tolist()
            if nonzero.any() else None)
    return result


def verify_positions(original, corrected, token_count):
    a = np.asarray(original, dtype=np.int32).reshape(4, token_count)
    b = np.asarray(corrected, dtype=np.int32).reshape(4, token_count)
    if not np.array_equal(a[:3], b[:3]) or np.any(a[3]) or not np.array_equal(b[3], b[0]):
        raise ValueError("position difference is not exclusively fourth-axis zero -> T")
    return dict(first_three_axes_identical=True, original_fourth_axis_all_zero=True,
                corrected_fourth_axis_equals_t=True, changed_positions=int(np.count_nonzero(a != b)))


def compare_runs(reference, candidate, corrected):
    identifiers = {}
    for name in ("input-ids", "token-types"):
        a = json.loads((reference / f"{name}.json").read_text())
        b = json.loads((candidate / f"{name}.json").read_text())
        if a != b:
            raise ValueError(f"{name} differ between runs")
        identifiers[name] = a
    original_positions = json.loads((reference / "positions.json").read_text())
    candidate_positions = json.loads((candidate / "positions.json").read_text())
    if corrected:
        positions = verify_positions(original_positions, candidate_positions, len(identifiers["input-ids"]))
    else:
        if original_positions != candidate_positions:
            raise ValueError("repeat positions differ")
        positions = dict(all_axes_identical=True)
    names = ["preprocessed", "vision-input"] + [f"vision-output-{i}" for i in range(4)]
    names += ["text-hidden", "conditioning"]
    tensors = {name: compare(read_tensor(reference / name), read_tensor(candidate / name)) for name in names}
    if not tensors["preprocessed"]["byte_identical"] or not tensors["vision-input"]["byte_identical"]:
        raise ValueError("input preprocessing differs")
    a = read_tensor(reference / "conditioning").reshape(-1, read_tensor(reference / "conditioning").shape[-1])
    b = read_tensor(candidate / "conditioning").reshape(a.shape)
    slots = np.array(identifiers["token-types"])
    if slots.shape != (a.shape[0],):
        raise ValueError("token slot count differs from conditioning")
    groups = {}
    for label, mask in (("image_tokens", slots > 0), ("text_and_special_tokens", slots == 0)):
        if mask.any():
            groups[label] = compare(a[mask], b[mask])
    return dict(input_ids_identical=True, token_types_identical=True,
                input_token_count=len(identifiers["input-ids"]), positions=positions,
                tensors=tensors, final_conditioning_groups=groups)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def limits():
    root = Path("/sys/fs/cgroup")
    memory, swap, cpu = [(root / name).read_text().strip() for name in
                         ("memory.max", "memory.swap.max", "cpu.max")]
    quota, period = cpu.split()
    if memory == "max" or int(memory) > 16 * 1024**3 or swap != "0":
        raise ValueError("requires <=16 GiB memory and zero swap")
    if quota == "max" or int(quota) / int(period) > 4:
        raise ValueError("requires <=4 CPUs")
    return dict(memory_max=memory, swap_max=swap, cpu_max=cpu)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    cgroup = limits()
    if not args.input.is_file() or not args.prompt_file.is_file():
        parser.error("input PNG and prompt file must exist")
    args.output_dir.mkdir(exist_ok=False)
    report = dict(version="0.3.0", cgroup=cgroup, runs=[], input_sha256=digest(args.input),
                  prompt_sha256=digest(args.prompt_file), prompt=args.prompt_file.read_text(),
                  loaded_components=["text_encoder", "vision_encoder", "projector"],
                  diffusion_loaded=False, vae_loaded=False, sampling=False,
                  comparison="native original vs fourth=T correction, plus original repeat")

    def record():
        report["elapsed_seconds"] = time.monotonic() - started
        report["memory_peak_bytes"] = int(Path("/sys/fs/cgroup/memory.peak").read_text())
        report["memory_events"] = dict(line.split() for line in
                                      Path("/sys/fs/cgroup/memory.events").read_text().splitlines())
        (args.output_dir / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    record()
    try:
        report["weights_sha256"] = {
            name: digest(Path("/models") / name) for name in
            ("Qwen3VL-8B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-8B-Instruct-F16.gguf")}
        record()
        for name, mode in (("original", "original"), ("corrected", "corrected"), ("repeat", "original")):
            run_start = time.monotonic()
            command = ["/sd.cpp/bin/sd-qwen21-conditioning", "--input", str(args.input.resolve()),
                       "--prompt-file", str(args.prompt_file.resolve()), "--output-dir",
                       str((args.output_dir / name).resolve()), "--position-mode", mode]
            print(f"starting {name}", flush=True)
            result = subprocess.run(command, check=False)
            report["runs"].append(dict(name=name, mode=mode, exit_code=result.returncode,
                                       seconds=time.monotonic() - run_start))
            record()
            result.check_returncode()
            if name != "original":
                report[name] = compare_runs(args.output_dir / "original", args.output_dir / name,
                                             corrected=name == "corrected")
                record()
        report["complete"] = True
        record()
        print(json.dumps({name: report[name]["tensors"]["conditioning"] for name in ("corrected", "repeat")}), flush=True)
    except Exception as exc:
        report["error"] = str(exc)
        record()
        raise


if __name__ == "__main__":
    main()
