#ifndef __SD_PIPELINE_REFERENCE_IMAGE_H__
#define __SD_PIPELINE_REFERENCE_IMAGE_H__

#include <algorithm>
#include <cmath>

#include "model/diffusion/model.hpp"

namespace sd::pipeline {

    inline sd::Tensor<float> resize_reference_for_vae(const sd::Tensor<float>& image,
                                                      SDVersion version,
                                                      int width,
                                                      int height,
                                                      const RefImageParams& params) {
        double vae_width;
        double vae_height;
        if (params.resize_vae_to_target) {
            vae_width  = width;
            vae_height = height;
        } else {
            int default_pixels = version == VERSION_QWEN_IMAGE_2_1 ? width * height : 1024 * 1024;
            int target_pixels  = params.vae_input_max_pixels > 0 ? params.vae_input_max_pixels : default_pixels;
            int vae_image_size = std::min(target_pixels, width * height);
            vae_width          = sqrt(vae_image_size * image.shape()[0] / image.shape()[1]);
            vae_height         = vae_width * image.shape()[1] / image.shape()[0];
        }
        int factor = sd_version_is_qwen_image(version) ? 32 : 16;
        vae_height = round(vae_height / factor) * factor;
        vae_width  = round(vae_width / factor) * factor;
        return sd::ops::interpolate(image,
                                    {static_cast<int>(vae_width), static_cast<int>(vae_height),
                                     image.shape()[2], image.shape()[3]});
    }

}  // namespace sd::pipeline

#endif  // __SD_PIPELINE_REFERENCE_IMAGE_H__
