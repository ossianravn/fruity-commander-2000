"""Preserve opaque plugin state and channel attribution across FL event framing."""

import struct
import unittest

from scripts.generator_presets import encode_event, parse, preset_image


def image(events):
    data = b"".join(encode_event(event, value) for event, value in events)
    return b"FLhd\x06\0\0\0\x30\0\x02\0\x30\0FLdt" + struct.pack("<I", len(data)) + data


class PresetTest(unittest.TestCase):
    def test_extracts_exact_channel_state_and_rejects_truncated_source(self):
        envelope = [(199, b"11.5.5\0"), (28, b"\x01"), (201, b"Wrapper"),
                    (212, b"config"), (203, b"name"), (213, b"blank")]
        state = b"opaque\0external/project.xpj" * 8
        source = image([(199, b"26.1.6.5639\0"), (172, b"\x01\x01\0"), (64, b"\x05\0"),
                        *envelope[2:5], (213, state), (236, b"mixer"), (213, b"effect")])
        actual = preset_image(source, 5, image(envelope))
        self.assertEqual(parse(actual)[1], [(199, b"26.1.6.5639\0")] + envelope[1:-1] + [(213, state)])
        with self.assertRaisesRegex(ValueError, "complete generator"):
            preset_image(source, 6, image(envelope))
        with self.assertRaisesRegex(ValueError, "length"):
            preset_image(source[:-1], 5, image(envelope))


if __name__ == "__main__":
    unittest.main()
