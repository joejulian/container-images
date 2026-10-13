"""Model-free tests: meta-device shapes only, no checkpoint or inference."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from latent_parity import ROOT, AutoencoderKLQwenImage21, compare, convert_weights, read_tensor, renamed


class ComparisonTests(unittest.TestCase):
    def test_layout_preserves_channels_and_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            stem = Path(directory) / "tensor"
            stem.with_suffix(".json").write_text(json.dumps(dict(
                dtype="<f4", layout="ggml_first_axis_contiguous", shape=[3, 2, 4, 1])))
            np.arange(24, dtype="<f4").tofile(stem.with_suffix(".f32"))
            actual = read_tensor(stem)
            self.assertEqual(actual.shape, (1, 4, 1, 2, 3))
            self.assertEqual(actual[0, 2, 0, 1, 2], 17)

    def test_nonfinite_values_are_retained(self):
        a = np.zeros((1, 2, 1, 2, 2), dtype=np.float32)
        b = a.copy()
        a[0, 0, 0, 0, 0] = np.nan
        result = compare(a, b)
        self.assertFalse(result["valid"])
        self.assertEqual(result["actual"]["nan"], 1)
        self.assertTrue(np.isnan(a[0, 0, 0, 0, 0]))

    def test_known_error_and_channel_metrics(self):
        reference = np.ones((1, 2, 1, 2, 2), dtype=np.float32)
        result = compare(reference * 2, reference)
        self.assertEqual(result["rmse"], 1)
        self.assertEqual(result["relative_rmse"], 1)
        self.assertEqual(result["per_channel_rmse"], [1, 1])
        with self.assertRaises(ValueError):
            compare(reference, reference[:, :1])

    def test_mapping_and_singleton_conversion(self):
        with torch.device("meta"):
            vae = AutoencoderKLQwenImage21.from_config(json.loads((ROOT / "vae-config.json").read_text()))
        expected = vae.state_dict()
        examples = {
            "encoder.downsamples.0.downsamples.0.residual.0.gamma": "encoder.down_blocks.0.resnets.0.norm1.gamma",
            "encoder.downsamples.1.downsamples.2.time_conv.weight": "encoder.down_blocks.1.downsampler.time_conv.weight",
            "decoder.upsamples.0.upsamples.3.resample.1.weight": "decoder.up_blocks.0.upsampler.resample.1.weight",
            "decoder.middle.2.residual.2.weight": "decoder.mid_block.resnets.1.conv1.weight",
            "conv1.weight": "quant_conv.weight",
        }
        for original, target in examples.items():
            self.assertEqual(renamed(original), target)
            self.assertIn(target, expected)
        with torch.device("meta"):
            original = {"conv1.weight": torch.empty((128, 128, 1, 1, 1), dtype=torch.bfloat16)}
        actual, mapping = convert_weights(original, {"quant_conv.weight": expected["quant_conv.weight"]})
        self.assertEqual(actual["quant_conv.weight"].shape, (128, 128, 1, 1))
        self.assertTrue(mapping[0]["squeeze_temporal_axis"])
        with self.assertRaises(ValueError):
            convert_weights(original, expected)
        with self.assertRaises(ValueError):
            convert_weights({"unknown": original["conv1.weight"]}, expected)
        with torch.device("meta"):
            original["conv1.weight"] = torch.empty((128, 128, 2, 1, 1))
        with self.assertRaises(ValueError):
            convert_weights(original, {"quant_conv.weight": expected["quant_conv.weight"]})


if __name__ == "__main__":
    unittest.main()
