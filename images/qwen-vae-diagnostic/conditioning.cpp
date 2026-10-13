#include "diagnostic_common.h"
#include "conditioning/conditioner.hpp"

static constexpr const char* TEXT_PATH = "/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf";
static constexpr const char* VISION_PATH = "/models/mmproj-Qwen3VL-8B-Instruct-F16.gguf";

static void dump_integers(const fs::path& path, const std::vector<int32_t>& values) {
    std::ofstream file(path);
    file << '[';
    for (size_t i = 0; i < values.size(); ++i) file << (i ? "," : "") << values[i];
    file << "]\n";
    file.close();
    require(file.good(), "integer export failed: " + path.string());
}

static void encode(const fs::path& input_path, const fs::path& prompt_path,
                   const fs::path& output_dir, bool corrected) {
    require(fs::is_regular_file(input_path) && fs::is_regular_file(prompt_path),
            "input PNG and prompt file must exist");
    std::ifstream png(input_path, std::ios::binary);
    unsigned char signature[8]{};
    png.read(reinterpret_cast<char*>(signature), sizeof(signature));
    const unsigned char expected[] = {137, 80, 78, 71, 13, 10, 26, 10};
    require(png.gcount() == 8 && std::memcmp(signature, expected, 8) == 0,
            "input is not a PNG");
    std::ifstream prompt_stream(prompt_path);
    const std::string prompt((std::istreambuf_iterator<char>(prompt_stream)), {});
    require(!prompt.empty(), "prompt file is empty");
    require(!fs::exists(output_dir) && fs::create_directory(output_dir),
            "output directory must be new and its parent must exist");
    FILE* log = std::fopen((output_dir / "diagnostic.log").c_str(), "wx");
    require(log != nullptr, "cannot create log");
    require(dup2(fileno(log), STDOUT_FILENO) >= 0 && dup2(fileno(log), STDERR_FILENO) >= 0,
            "cannot redirect log");
    std::fclose(log);
    setvbuf(stdout, nullptr, _IOLBF, 0);
    setvbuf(stderr, nullptr, _IONBF, 0);
    std::cout << std::setprecision(12);
    sd_set_log_callback([](sd_log_level_t, const char* message, void*) {
        std::fputs(message, stderr);
        std::fflush(stderr);
    }, nullptr);
    const auto all_start = Clock::now();
    print_provenance();
    verify_limits();
    std::cout << "position_mode=" << (corrected ? "corrected" : "original")
              << " model_version=VERSION_QWEN_IMAGE_2_1 text=" << TEXT_PATH
              << " vision_projector=" << VISION_PATH << '\n'
              << "constructed_components=text,vision,projector diffusion=absent vae=absent sampling=none noise=none\n"
              << "backend=Vulkan0 weight_placement=cpu threads=4 target=1024x1024 "
                 "flash_attention=true precision=production_tensor_types mmap=false eager_load=false "
                 "segmented_compute=true prefetch=true tokenizer=production_Qwen2Tokenizer\n";
    sd::ParallelExecutor executor(THREADS);
    sd::ParallelScope scope(&executor);
    auto start = Clock::now();
    SDImageOwner input;
    require(load_sd_image_from_file(input.put(), input_path.c_str(), 0, 0, 0), "PNG load failed");
    sd_image_t reference = input.get();
    sd_img_gen_params_t params;
    sd_img_gen_params_init(&params);
    params.ref_images = &reference;
    params.ref_images_count = 1;
    sd::ImagePreprocessor preprocessing(params.image_preprocess.rules);
    require(preprocessing.prepare_inputs(params, TARGET_SIZE, TARGET_SIZE), "reference preprocessing failed");
    auto image = sd::pipeline::ensure_image_tensor_channels(sd_image_to_tensor(params.ref_images[0]), 4);
    image = sd::pipeline::resize_reference_for_vae(image, VERSION, TARGET_SIZE, TARGET_SIZE,
                                                  REF_IMAGE_PRESETS.at("qwen"));
    dump_tensor(output_dir / "preprocessed", image);
    checkpoint("preprocessed", image);
    save_png(output_dir / "preprocessed.png", image);
    elapsed("reference_preprocessing", start);

    start = Clock::now();
    SDBackendManager backends;
    std::string error;
    require(backends.init("Vulkan0", "*=cpu", "", &error), "backend setup failed: " + error);
    auto compute = backends.runtime_backend(SDBackendModule::TE);
    auto storage = backends.params_backend(SDBackendModule::TE);
    require(compute && storage, "text/vision backend unavailable");
    const std::string device = ggml_backend_dev_description(ggml_backend_get_device(compute));
    require(device.find("B580") != std::string::npos && !sd_backend_is_cpu(compute) && sd_backend_is_cpu(storage),
            "required B580 Vulkan compute / CPU weight placement not selected");
    std::cout << "device=" << device << " compute_backend=" << ggml_backend_name(compute)
              << " weight_backend=" << ggml_backend_name(storage) << std::endl;
    auto manager = std::make_shared<ModelManager>();
    manager->set_n_threads(THREADS);
    manager->set_enable_mmap(false);
    manager->set_writable_mmap(false);
    manager->set_segmented_compute_disabled(false);
    manager->set_prefetch_disabled(false);
    ModelLoader loader;
    require(loader.init_from_file(TEXT_PATH, "text_encoders.llm."), "text loader failed");
    require(loader.init_from_file_and_convert_name(VISION_PATH, "text_encoders.llm.visual.", VERSION),
            "vision loader failed");
    for (const auto& entry : loader.get_wtype_stat())
        std::cout << "stored_weight_dtype=" << ggml_type_name(entry.first) << " tensors=" << entry.second << '\n';
    require(manager->set_loader(std::move(loader)), "model manager initialization failed");
    manager->prepare_file_io();
    // Same constructor as model_builders.cpp's Qwen branch, without constructing its diffusion runner.
    LLMEmbedder conditioner(compute, manager->loader().get_tensor_storage_map(), VERSION, "", true, manager);
    require(conditioner.llm->config.arch == LLM::LLMArch::QWEN3_VL && !conditioner.byt5,
            "unexpected conditioner architecture");
    conditioner.set_flash_attention_enabled(true);
    conditioner.set_max_graph_vram_bytes(0);
    std::map<std::string, ggml_tensor*> weights;
    std::map<ggml_tensor*, enum ggml_op> operations;
    conditioner.get_param_tensors(weights);
    conditioner.get_param_tensor_ops(operations);
    require(manager->register_param_tensors(ModelComponent::Conditioner, weights,
                ModelManager::ResidencyMode::ParamBackend, compute, storage, nullptr, false, false, &operations),
            "conditioner registration failed");
    require(manager->validate_registered_tensors(), "conditioner tensor validation failed");
    std::map<ggml_type, size_t> types;
    for (const auto& entry : weights) ++types[entry.second->type];
    for (const auto& entry : types)
        std::cout << "runtime_weight_dtype=" << ggml_type_name(entry.first) << " tensors=" << entry.second << '\n';
    std::cout << "registered_components=Conditioner registered_parameter_bytes="
              << manager->registered_params_size({ModelComponent::Conditioner}) << std::endl;
    elapsed("model_metadata_and_registration", start);

    conditioner.llm->diagnostic_correct_qwen3_positions = corrected;
    int vision_calls = 0, text_calls = 0;
    auto vision_start = Clock::now();
    conditioner.llm->diagnostic_vision_observer = [&](const sd::Tensor<float>& rgb,
                                                       const std::vector<sd::Tensor<float>>& outputs) {
        require(++vision_calls == 1 && outputs.size() == 4, "unexpected vision output count");
        elapsed("vision_including_lazy_weight_loading", vision_start);
        dump_tensor(output_dir / "vision-input", rgb);
        checkpoint("vision_input_minus1_to_1", rgb);
        for (size_t i = 0; i < outputs.size(); ++i) {
            const auto name = "vision-output-" + std::to_string(i);
            dump_tensor(output_dir / name, outputs[i]);
            checkpoint(name.c_str(), outputs[i]);
        }
        start = Clock::now();
    };
    conditioner.llm->diagnostic_text_observer = [&](const sd::Tensor<int32_t>& ids,
                                                     const sd::Tensor<float>& hidden) {
        require(++text_calls == 1, "unexpected text forward count");
        elapsed("text_including_lazy_weight_loading", start);
        dump_integers(output_dir / "input-ids.json", ids.values());
        dump_tensor(output_dir / "text-hidden", hidden);
        checkpoint("text_hidden_before_token_weighting_and_prefix_crop", hidden);
    };
    std::vector<sd::Tensor<float>> references{std::move(image)};
    ConditionerParams conditioning;
    conditioning.text = prompt;
    conditioning.width = TARGET_SIZE;
    conditioning.height = TARGET_SIZE;
    conditioning.ref_images = &references;
    conditioning.ref_image_params = REF_IMAGE_PRESETS.at("qwen");
    const auto condition = conditioner.get_learned_condition(THREADS, conditioning);
    require(vision_calls == 1 && text_calls == 1, "missing diagnostic checkpoints");
    dump_tensor(output_dir / "conditioning", condition.c_crossattn);
    checkpoint("final_diffusion_conditioning", condition.c_crossattn);
    dump_integers(output_dir / "token-types.json", condition.c_token_types.values());
    dump_integers(output_dir / "positions.json", conditioner.llm->input_pos_vec);
    conditioner.runner_end();
    elapsed("total", all_start);
    std::cout << "result=success\n";
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--version") {
            std::cout << DIAGNOSTIC_VERSION << '\n';
            return 0;
        }
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "Usage: sd-qwen21-conditioning --input INPUT_PNG --prompt-file PROMPT_FILE "
                         "--output-dir NEW_RESULTS_DIR --position-mode original|corrected\n"
                         "Loads only text/vision/projector, Vulkan0/B580, CPU weights, four threads. "
                         "Requires <=16 GiB memory, zero swap, and exclusive GPU access.\n";
            return 0;
        }
        std::map<std::string, std::string> args;
        for (int i = 1; i < argc; i += 2) {
            const std::string key = argv[i];
            require(i + 1 < argc && (key == "--input" || key == "--prompt-file" ||
                    key == "--output-dir" || key == "--position-mode") && !args.count(key),
                    "unknown, duplicate, or incomplete argument: " + key);
            args[key] = argv[i + 1];
        }
        require(args.size() == 4 && (args["--position-mode"] == "original" ||
                    args["--position-mode"] == "corrected"), "all four arguments and a valid position mode are required");
        encode(fs::absolute(args.at("--input")), fs::absolute(args.at("--prompt-file")),
               fs::absolute(args.at("--output-dir")), args.at("--position-mode") == "corrected");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "result=failed error=" << error.what() << std::endl;
        return 1;
    }
}
