#!/usr/bin/env python3
"""Compile and exercise the actual position-building block without model weights."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-original", action="store_true")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = (args.source / "src/model/te/llm.hpp").read_text()
    start = source.index("            int64_t n_tokens = input_ids->ne[0];", source.index("struct LLMRunner"))
    end = source.index("            auto input_pos = ggml_new_tensor_1d", start)
    block = source[start:end]
    fixture = r'''
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#define GGML_ASSERT(x) do { if (!(x)) std::abort(); } while (0)
enum class LLMArch { MISTRAL_SMALL_3_2, MINISTRAL_3_3B, QWEN3, GEMMA3_12B,
    GEMMA4_12B, GEMMA2_2B, GPT_OSS_20B, LLADA2_MOE, QWEN3_VL, QWEN2_5_VL };
struct Grid { int index, size, grid_h, grid_w; };
std::vector<int> positions(LLMArch arch, int count, const std::vector<Grid>& image_grids) {
    struct { LLMArch arch; struct { int spatial_merge_size; } vision; } config{arch, {2}};
    struct Tensor { int64_t ne[1]; } tensor{{count}};
    auto input_ids = &tensor;
    std::vector<int> input_pos_vec;
    /* PRODUCTION_BLOCK */
    return input_pos_vec;
}
int mismatches = 0;
void check(bool condition, const char* reason) {
    if (!condition) { std::fprintf(stderr, "%s\n", reason); ++mismatches; }
}
void check_tail(const std::vector<int>& p, int n) {
    check(p.size() == static_cast<size_t>(4*n), "four position axes required");
    for (int i=0; i<n; ++i) check(p[3*n+i] == p[i], "fourth axis must equal final T");
}
int main() {
    auto text = positions(LLMArch::QWEN3_VL, 9, {});
    check_tail(text, 9);
    for (int i=0; i<9; ++i) {
        check(text[i] == i && text[9+i] == i && text[18+i] == i, "text THW changed");
    }
    // Reference grid is 64x64 patches, merged to 32x32 image tokens.
    auto square = positions(LLMArch::QWEN3_VL, 1040, {{5, 1024, 64, 64}});
    check_tail(square, 1040);
    check(square[5] == 5 && square[1028] == 5 && square[1029] == 37, "square T boundary");
    check(square[1040+1028] == 36 && square[2080+1028] == 36, "square HW boundary");
    auto rect = positions(LLMArch::QWEN3_VL, 35, {{3, 24, 8, 12}});
    check_tail(rect, 35);
    check(rect[26] == 3 && rect[27] == 9, "rectangular T boundary");
    check(rect[35+26] == 6 && rect[70+26] == 8, "rectangular HW boundary");
    auto multi = positions(LLMArch::QWEN3_VL, 40, {{3, 24, 8, 12}, {30, 6, 4, 6}});
    check_tail(multi, 40);
    check(multi[30] == 12 && multi[35] == 12 && multi[36] == 15, "second image T boundary");
    check(multi[40+35] == 13 && multi[80+35] == 14, "second image HW boundary");
    auto other = positions(LLMArch::QWEN2_5_VL, 9, {});
    for (int i=0; i<9; ++i) {
        check(other[i] == i && other[9+i] == i && other[18+i] == i && other[27+i] == 0,
              "Qwen2.5-VL behavior changed");
    }
    auto single = positions(LLMArch::QWEN3, 9, {});
    check(single.size() == 9, "Qwen3 one-axis path changed");
    for (int i=0; i<9; ++i) check(single[i] == i, "Qwen3 position changed");
    return mismatches ? 1 : 0;
}
'''.replace("/* PRODUCTION_BLOCK */", block)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        (path / "positions.cpp").write_text(fixture)
        subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(path / "positions.cpp"), "-o", str(path / "positions")], check=True)
        result = subprocess.run([str(path / "positions")], capture_output=True, text=True)
        if args.expect_original:
            errors = result.stderr.splitlines()
            assert result.returncode == 1 and errors
            assert set(errors) == {"fourth axis must equal final T"}, result.stderr
            print(f"Original reproduces {len(errors)} temporal-tail mismatches; other checks pass")
        else:
            assert result.returncode == 0, result.stderr
            print("Patched production block passes all six position fixtures")


if __name__ == "__main__":
    main()
