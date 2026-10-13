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
#include "model/vae/vae.hpp"
#include "model_loader.h"
#include "model_manager.h"
#include "pipeline/generation.h"
#include "pipeline/model_builders.h"
#include "pipeline/reference_image.h"
#include "runtime/image_preprocess.h"

namespace fs = std::filesystem;
using Clock  = std::chrono::steady_clock;

static constexpr const char* DIAGNOSTIC_VERSION = "0.2.0";
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

static void self_test() {
    auto values = sd::Tensor<float>::from_vector(
        {1, 2, 3, std::numeric_limits<float>::quiet_NaN(),
         std::numeric_limits<float>::infinity(),
         -std::numeric_limits<float>::infinity()});
    auto stats = measure(values);
    require(stats.finite == 3 && stats.nan == 1 && stats.pos_inf == 1 &&
                stats.neg_inf == 1 && !stats.valid(),
            "invalid-value counters");
    require(stats.min == 1 && stats.max == 3 && stats.mean == 2 &&
                std::abs(stats.stddev() - std::sqrt(2.0 / 3.0)) < 1e-12,
            "finite statistics");
    require(std::isnan(values[3]) && std::isinf(values[4]),
            "statistics mutated input");

    auto rgba    = sd::full<float>({1024, 1024, 4, 1}, 0.5f);
    auto resized = sd::pipeline::resize_reference_for_vae(
        rgba, VERSION, 1024, 1024, REF_IMAGE_PRESETS.at("qwen"));
    require(resized.shape() == rgba.shape() && resized[0] == rgba[0],
            "square reference resize");
    auto landscape         = sd::full<float>({64, 32, 4, 1}, 0.5f);
    auto resized_landscape = sd::pipeline::resize_reference_for_vae(
        landscape, VERSION, 1024, 1024, REF_IMAGE_PRESETS.at("qwen"));
    require(resized_landscape.shape()[0] == 1440 &&
                resized_landscape.shape()[1] == 736,
            "aspect ratio and multiple-of-32 rounding");

    uint8_t pixels[] = {0, 127, 255, 255};
    sd_image_t input{1, 1, 4, pixels};
    sd_img_gen_params_t params;
    sd_img_gen_params_init(&params);
    params.ref_images       = &input;
    params.ref_images_count = 1;
    sd::ImagePreprocessor preprocessing;
    require(preprocessing.prepare_inputs(params, 1024, 1024),
            "reference preprocessing failed");
    require(
        params.ref_images[0].width == 1 && params.ref_images[0].channel == 4 &&
            std::memcmp(params.ref_images[0].data, pixels, sizeof(pixels)) == 0,
        "default reference preprocessing changed pixels");
    require(pixels[1] == 127, "reference input was modified");
    std::cout
        << "self-test passed: statistics, invalid-value preservation, native "
           "reference preprocessing and resize; no models or backends loaded\n";
}

static void roundtrip(const fs::path& input_path, const fs::path& output_dir, bool export_latents) {
    require(fs::is_regular_file(input_path),
            "input must be an existing regular PNG file");
    std::ifstream input_stream(input_path, std::ios::binary);
    unsigned char signature[8]{};
    input_stream.read(reinterpret_cast<char*>(signature), sizeof(signature));
    const unsigned char png_signature[] = {137, 80, 78, 71, 13, 10, 26, 10};
    require(input_stream.gcount() == 8 &&
                std::memcmp(signature, png_signature, 8) == 0,
            "input is not a PNG");
    require(!fs::exists(output_dir) && fs::create_directory(output_dir),
            "output directory must be new and its parent must exist");
    const auto log_path = output_dir / "diagnostic.log";
    std::cerr << "Writing diagnostic output to " << output_dir << std::endl;
    FILE* log = std::fopen(log_path.c_str(), "wx");
    require(log != nullptr, "cannot create diagnostic.log");
    require(dup2(fileno(log), STDOUT_FILENO) >= 0 &&
                dup2(fileno(log), STDERR_FILENO) >= 0,
            "cannot redirect diagnostic log");
    std::fclose(log);
    setvbuf(stdout, nullptr, _IOLBF, 0);
    setvbuf(stderr, nullptr, _IONBF, 0);
    std::cout << std::setprecision(12);
    sd_set_log_callback(
        [](sd_log_level_t, const char* message, void*) {
            std::fputs(message, stderr);
            std::fflush(stderr);
        },
        nullptr);
    const auto all_start = Clock::now();
    print_provenance();
    verify_limits();
    std::cout
        << "input=" << input_path
        << " model_version=VERSION_QWEN_IMAGE_2_1 vae=" << VAE_PATH
        << " runtime_backend=Vulkan0 params_backend=cpu threads=4 "
           "target=1024x1024"
        << " flash_attention=true precision=production_tensor_types mmap=false "
           "eager_load=false"
        << " segmented_compute=true prefetch=true circular_axes=false "
           "temporal_tiling=false\n"
        << "tiling enabled=true tile_pixels=256x256 overlap=0.5 "
           "relative_sizes=0,0\n"
        << "constructed_components=VAE_only diffusion=absent text_encoder=absent "
           "vision_encoder=absent sampling=none noise=none\n"
        << "checkpoint_instrumentation=VAE::decoded_output_observer before "
           "scale_tensor_to_0_1; all checkpoints enabled\n";

    sd::ParallelExecutor executor(THREADS);
    sd::ParallelScope tensor_scope(&executor);
    auto start = Clock::now();
    SDImageOwner input;
    require(load_sd_image_from_file(input.put(), input_path.c_str(), 0, 0, 0),
            "PNG load failed");
    elapsed("load_png", start);
    start                = Clock::now();
    sd_image_t reference = input.get();
    sd_img_gen_params_t params;
    sd_img_gen_params_init(&params);
    params.ref_images       = &reference;
    params.ref_images_count = 1;
    sd::ImagePreprocessor preprocessing(params.image_preprocess.rules);
    require(preprocessing.prepare_inputs(params, TARGET_SIZE, TARGET_SIZE),
            "reference preprocessing failed");
    auto image = sd::pipeline::ensure_image_tensor_channels(
        sd_image_to_tensor(params.ref_images[0]), 4);
    image = sd::pipeline::resize_reference_for_vae(
        image, VERSION, TARGET_SIZE, TARGET_SIZE, REF_IMAGE_PRESETS.at("qwen"));
    if (export_latents)
        dump_tensor(output_dir / "preprocessed", image);
    checkpoint("preprocessed_input_0_to_1", image);
    save_png(output_dir / "preprocessed.png", image);
    elapsed("reference_preprocessing", start);

    start = Clock::now();
    SDBackendManager backends;
    std::string error;
    require(backends.init("Vulkan0", "*=cpu", "", &error),
            "backend setup failed: " + error);
    auto compute = backends.runtime_backend(SDBackendModule::VAE);
    auto storage = backends.params_backend(SDBackendModule::VAE);
    require(compute && storage, "VAE backend unavailable");
    const std::string device =
        ggml_backend_dev_description(ggml_backend_get_device(compute));
    require(
        device.find("B580") != std::string::npos && !sd_backend_is_cpu(compute) &&
            sd_backend_is_cpu(storage),
        "required B580 Vulkan compute / CPU weight placement was not selected");
    std::cout << "device=" << device
              << " compute_backend=" << ggml_backend_name(compute)
              << " weight_backend=" << ggml_backend_name(storage) << std::endl;

    auto manager = std::make_shared<ModelManager>();
    manager->set_n_threads(THREADS);
    manager->set_enable_mmap(false);
    manager->set_writable_mmap(false);
    manager->set_segmented_compute_disabled(false);
    manager->set_prefetch_disabled(false);
    ModelLoader loader;
    require(loader.init_from_file_and_convert_name(VAE_PATH, "vae.", VERSION),
            "VAE loader initialization failed");
    for (const auto& entry : loader.get_wtype_stat()) {
        std::cout << "stored_weight_dtype=" << ggml_type_name(entry.first)
                  << " tensors=" << entry.second << '\n';
    }
    require(manager->set_loader(std::move(loader)),
            "VAE model manager initialization failed");
    manager->prepare_file_io();
    sd_ctx_params_t context_params;
    sd_ctx_params_init(&context_params);
    context_params.vae_path   = VAE_PATH;
    context_params.n_threads  = THREADS;
    context_params.flash_attn = true;
    sd::model_builders::Context context{
        context_params, VERSION, manager->loader().get_tensor_storage_map(),
        backends, manager};
    sd::model_builders::VAERunners runners;
    require(sd::model_builders::build_vae_runners(context, {}, runners),
            "VAE construction failed");
    auto& vae = runners.vae;
    require(vae && !runners.preview && !runners.audio,
            "unexpected VAE runner selection");
    vae->set_flash_attention_enabled(true);
    vae->set_max_graph_vram_bytes(0);
    vae->set_circular_axes(false, false);
    require(manager->register_runner_params(
                ModelComponent::VAE, *vae,
                ModelManager::ResidencyMode::ParamBackend, compute, storage),
            "VAE registration failed");
    require(manager->validate_registered_tensors(),
            "VAE tensor validation failed");
    std::map<std::string, ggml_tensor*> weights;
    vae->get_param_tensors(weights);
    std::map<ggml_type, size_t> types;
    for (const auto& entry : weights) {
        ++types[entry.second->type];
    }
    for (const auto& entry : types) {
        std::cout << "runtime_weight_dtype=" << ggml_type_name(entry.first)
                  << " tensors=" << entry.second << '\n';
    }
    std::cout << "registered_components=VAE registered_parameter_bytes="
              << manager->registered_params_size({ModelComponent::VAE})
              << std::endl;
    elapsed("vae_initialization_metadata_and_registration", start);

    sd_tiling_params_t tiles{true, false, 256, 256, 0.5f, 0, 0, nullptr};
    int tile_w = 0, tile_h = 0;
    float overlap   = 0;
    const int scale = vae->get_scale_factor();
    require(vae->get_tile_sizes(tile_w, tile_h, overlap, tiles,
                                image.shape()[0] / scale,
                                image.shape()[1] / scale),
            "tile resolution failed");
    std::cout << "resolved_encode_tiles pixels=" << tile_w * scale << 'x'
              << tile_h * scale << " latent=" << tile_w << 'x' << tile_h
              << " overlap=" << overlap << " spatial_scale=" << scale
              << std::endl;
    size_t tile_index = 0;
    if (export_latents) {
        fs::create_directory(output_dir / "tiles");
        vae->encoded_tile_observer = [&](const sd::Tensor<float>& input_tile,
                                         const sd::Tensor<float>& output_tile) {
            const auto stem = output_dir / "tiles" / std::to_string(tile_index++);
            dump_tensor(stem.string() + "-input", input_tile);
            dump_tensor(stem.string() + "-raw", output_tile);
            dump_tensor(stem.string() + "-normalized",
                        vae->vae_to_diffusion_latents(
                            vae->vae_output_to_latents(output_tile, nullptr)));
        };
    }
    start        = Clock::now();
    auto encoded = vae->encode(THREADS, image, tiles, false, false);
    if (export_latents)
        dump_tensor(output_dir / "encoder-raw", encoded);
    checkpoint("encoder_output_before_diffusion_normalization", encoded);
    auto latents = vae->vae_output_to_latents(encoded, nullptr);
    elapsed("vae_encode_including_lazy_weight_loading", start);
    start           = Clock::now();
    auto normalized = vae->vae_to_diffusion_latents(latents);
    if (export_latents)
        dump_tensor(output_dir / "reference-normalized", normalized);
    checkpoint("diffusion_normalized_reference_latents", normalized);
    auto decoder_input = vae->diffusion_to_vae_latents(normalized);
    checkpoint("decoder_input_after_inverse_normalization", decoder_input);
    elapsed("production_latent_conversions", start);
    if (export_latents) {
        std::cout << "mode=latent_export encode_tiles=" << tile_index
                  << " decode=skipped\n";
        elapsed("total", all_start);
        std::cout << "result=success\n";
        return;
    }
    require(vae->get_tile_sizes(tile_w, tile_h, overlap, tiles,
                                decoder_input.shape()[0],
                                decoder_input.shape()[1]),
            "decode tile resolution failed");
    std::cout << "resolved_decode_tiles pixels=" << tile_w * scale << 'x'
              << tile_h * scale << " latent=" << tile_w << 'x' << tile_h
              << " overlap=" << overlap << std::endl;
    vae->decoded_output_observer = [](const sd::Tensor<float>& decoded) {
        checkpoint("decoded_output_before_clamping_minus1_to_1", decoded);
    };
    start = Clock::now();
    auto decoded =
        vae->decode(THREADS, decoder_input, tiles, false, false, false);
    require(!decoded.empty(), "VAE decode failed; no untiled retry permitted");
    elapsed("vae_decode_including_lazy_weight_loading", start);
    start = Clock::now();
    save_png(output_dir / "reconstructed.png", decoded);
    elapsed("write_reconstructed_png", start);
    elapsed("total", all_start);
    std::cout << "result=success\n";
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--version") {
            std::cout << DIAGNOSTIC_VERSION << '\n';
            return 0;
        }
        if (argc == 2 && std::string(argv[1]) == "--build-info") {
            print_provenance();
            return 0;
        }
        if (argc == 2 && std::string(argv[1]) == "--self-test") {
            self_test();
            return 0;
        }
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "Usage: sd-qwen21-vae-roundtrip --input INPUT_PNG "
                         "--output-dir NEW_RESULTS_DIR [--export-latents]\n"
                      << "Fixed profile: Qwen Image 2.1, Vulkan0/B580, CPU weights, "
                         "4 threads, 1024x1024 target,\n"
                      << "256x256 tiled encode/decode, overlap 0.5. Requires <=16 "
                         "GiB RAM cgroup and zero swap.\n"
                      << "--version, --build-info and --self-test do not load models "
                         "or GPU backends.\n";
            return 0;
        }
        std::string input, output;
        bool export_latents = false;
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--export-latents" && !export_latents) {
                export_latents = true;
                continue;
            }
            require(i + 1 < argc, "missing argument value");
            if (arg == "--input" && input.empty()) {
                input = argv[++i];
            } else if (arg == "--output-dir" && output.empty()) {
                output = argv[++i];
            } else {
                throw std::runtime_error("unknown or duplicate argument: " + arg);
            }
        }
        require(!input.empty() && !output.empty(),
                "--input and --output-dir are required");
        roundtrip(fs::absolute(input), fs::absolute(output), export_latents);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "result=failed error=" << error.what() << std::endl;
        return 1;
    }
}
