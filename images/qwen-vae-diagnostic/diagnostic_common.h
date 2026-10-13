#pragma once

#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

#include "common/media_io.h"
#include "common/resource_owners.hpp"
#include "core/ggml_extend_backend.h"
#include "core/parallel.h"
#include "core/util.h"
#include "model_loader.h"
#include "model_manager.h"
#include "pipeline/generation.h"
#include "pipeline/reference_image.h"
#include "runtime/image_preprocess.h"

namespace fs = std::filesystem;
using Clock  = std::chrono::steady_clock;

static constexpr const char* DIAGNOSTIC_VERSION = "0.3.0";
static constexpr const char* VAE_PATH =
    "/models/qwen_image_2.1_vae_bf16.safetensors";
static constexpr int THREADS       = 4;
static constexpr int TARGET_SIZE   = 1024;
static constexpr SDVersion VERSION = VERSION_QWEN_IMAGE_2_1;

struct TensorStats {
    int64_t finite  = 0;
    int64_t nan     = 0;
    int64_t pos_inf = 0;
    int64_t neg_inf = 0;
    double min      = std::numeric_limits<double>::infinity();
    double max      = -std::numeric_limits<double>::infinity();
    double mean     = 0;
    double m2       = 0;

    bool valid() const {
        return finite > 0 && nan == 0 && pos_inf == 0 && neg_inf == 0;
    }
    double stddev() const {
        return finite ? std::sqrt(m2 / finite)
                      : std::numeric_limits<double>::quiet_NaN();
    }
};

static void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

static TensorStats measure(const sd::Tensor<float>& tensor) {
    TensorStats stats;
    for (int64_t i = 0; i < tensor.numel(); ++i) {
        double value = tensor[i];
        if (std::isnan(value)) {
            ++stats.nan;
        } else if (std::isinf(value)) {
            value > 0 ? ++stats.pos_inf : ++stats.neg_inf;
        } else {
            ++stats.finite;
            stats.min    = std::min(stats.min, value);
            stats.max    = std::max(stats.max, value);
            double delta = value - stats.mean;
            stats.mean += delta / stats.finite;
            stats.m2 += delta * (value - stats.mean);
        }
    }
    return stats;
}

static void checkpoint(const char* name, const sd::Tensor<float>& tensor) {
    require(!tensor.empty(), std::string(name) + ": empty tensor");
    const auto stats = measure(tensor);
    std::cout << "checkpoint=" << name << " dtype=float32 shape=[";
    for (size_t i = 0; i < tensor.shape().size(); ++i) {
        std::cout << (i ? "," : "") << tensor.shape()[i];
    }
    std::cout << "] elements=" << tensor.numel()
              << " statistics_population=finite_only finite=" << stats.finite
              << " min=" << stats.min << " max=" << stats.max << " mean="
              << (stats.finite ? stats.mean
                               : std::numeric_limits<double>::quiet_NaN())
              << " stddev=" << stats.stddev() << " nan=" << stats.nan
              << " positive_inf=" << stats.pos_inf
              << " negative_inf=" << stats.neg_inf << std::endl;
    require(stats.valid(),
            std::string(name) +
                ": invalid numerical values; refusing to hide "
                "them in PNG conversion");
}

// Preserve the actual float values, including non-finite values, for
// comparison.
static void dump_tensor(const fs::path& stem, const sd::Tensor<float>& tensor) {
    const uint16_t one = 1;
    require(*reinterpret_cast<const uint8_t*>(&one) == 1 && sizeof(float) == 4,
            "tensor export requires little-endian float32");
    std::ofstream data(stem.string() + ".f32", std::ios::binary);
    data.write(reinterpret_cast<const char*>(tensor.data()),
               tensor.numel() * sizeof(float));
    data.close();
    require(data.good(), "tensor export failed: " + stem.string());
    std::ofstream meta(stem.string() + ".json");
    meta << "{\"dtype\":\"<f4\",\"layout\":\"ggml_first_axis_contiguous\","
            "\"shape\":[";
    for (size_t i = 0; i < tensor.shape().size(); ++i) {
        meta << (i ? "," : "") << tensor.shape()[i];
    }
    meta << "]}\n";
    meta.close();
    require(meta.good(), "tensor metadata export failed");
}

static void elapsed(const char* stage, Clock::time_point start) {
    std::cout << "stage=" << stage << " seconds="
              << std::chrono::duration<double>(Clock::now() - start).count()
              << std::endl;
}

static std::string read_line(const fs::path& path) {
    std::ifstream file(path);
    require(file.good(), "cannot read " + path.string());
    std::string result;
    std::getline(file, result);
    return result;
}

static void verify_limits() {
    const auto memory = read_line("/sys/fs/cgroup/memory.max");
    const auto swap   = read_line("/sys/fs/cgroup/memory.swap.max");
    const auto cpu    = read_line("/sys/fs/cgroup/cpu.max");
    std::cout << "cgroup memory.max=" << memory << " memory.swap.max=" << swap
              << " cpu.max=" << cpu << std::endl;
    require(memory != "max" && std::stoull(memory) <= 17179869184ULL,
            "a cgroup memory limit no greater than 16 GiB is required");
    require(swap == "0", "a zero-swap cgroup limit is required");
    std::istringstream quota(cpu);
    uint64_t limit = 0, period = 0;
    require(bool(quota >> limit >> period) && period > 0 &&
                double(limit) / period <= THREADS,
            "a cgroup CPU limit no greater than four CPUs is required");
}

static void save_png(const fs::path& path, const sd::Tensor<float>& tensor) {
    SDImageOwner image(tensor_to_sd_image(tensor));
    require(image.get().data != nullptr, "image conversion failed");
    require(write_image_to_file(path.string(), image.get().data,
                                image.get().width, image.get().height,
                                image.get().channel),
            "PNG write failed: " + path.string());
}

static void print_provenance() {
    std::cout << "diagnostic_version=" << DIAGNOSTIC_VERSION
              << " upstream_sha=" << DIAGNOSTIC_UPSTREAM_SHA << '\n';
    std::ifstream file("/opt/vae-diagnostic/build-provenance.txt");
    require(file.good(), "missing container build provenance");
    std::cout << file.rdbuf() << std::endl;
}

