import unittest

import numpy as np

from ingestion.frame.anchor import Anchor
from ingestion.frame.normalizer import Normalizer


class TestColorStandard(unittest.TestCase):
    def test_normalizer_rgb_input_to_bgr_output(self):
        frame_rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        frame_rgb[0, 0] = [10, 20, 30]  # RGB
        normalizer = Normalizer((2, 2), frame_color="rgb")
        out = normalizer.process(frame_rgb)
        self.assertEqual(out[0, 0].tolist(), [30, 20, 10])

    def test_anchor_color_conversion_differs(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        frame[:, :4] = [255, 0, 0]  # Red in RGB
        frame[:, 4:] = [0, 0, 255]  # Blue in RGB
        anchor = Anchor()
        rgb_hash = anchor.generate(frame, frame_color="rgb")
        bgr_hash = anchor.generate(frame, frame_color="bgr")
        self.assertNotEqual(rgb_hash, bgr_hash)


if __name__ == "__main__":
    unittest.main()
