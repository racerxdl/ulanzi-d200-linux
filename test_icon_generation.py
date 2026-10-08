"""Consumer-visible icon rendering and unsupported-type rejection tests."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops

from ulanzi_manager.icon_generator import IconGenerator, IconSpec


class IconGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.cache_dir = Path(self.temporary_directory.name)
        self.generator = IconGenerator(cache_dir=self.cache_dir)

    def test_unsupported_types_are_rejected_without_cached_images(self):
        for icon_type in ('emoji', 'icon', 'unknown'):
            for from_dict in (False, True):
                with self.subTest(icon_type=icon_type, from_dict=from_dict):
                    spec = {'type': icon_type}
                    with self.assertRaisesRegex(ValueError, icon_type):
                        if from_dict:
                            self.generator.generate_from_dict(spec)
                        else:
                            self.generator.generate(IconSpec(spec))
        self.assertEqual(list(self.cache_dir.iterdir()), [])

    def test_unsupported_types_are_rejected_with_matching_cached_images(self):
        for icon_type in ('emoji', 'icon', 'unknown'):
            spec = IconSpec({'type': icon_type})
            for button_index in (None, 7):
                cache_path = self.cache_dir / (
                    f'icon_{spec.get_hash()}.png' if button_index is None
                    else f'button_icon_{button_index}.png'
                )
                Image.new('RGB', (9, 5), '#123456').save(cache_path)
                cached_bytes = cache_path.read_bytes()
                for from_dict in (False, True):
                    with self.subTest(icon_type=icon_type, button_index=button_index,
                                      from_dict=from_dict):
                        with self.assertRaisesRegex(ValueError, icon_type):
                            if from_dict:
                                self.generator.generate_from_dict(
                                    spec.spec_dict, button_index=button_index)
                            else:
                                self.generator.generate(spec, button_index=button_index)
                        self.assertEqual(cache_path.read_bytes(), cached_bytes)

    def test_solid_icon_has_requested_color_and_geometry(self):
        path = self.generator.generate_from_dict({
            'type': 'solid', 'color': '#0066FF', 'size': [37, 23],
        })
        with Image.open(path) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (37, 23))
            self.assertEqual(image.getcolors(), [(37 * 23, (0, 102, 255))])

    def test_gradient_icon_has_vertical_color_transition(self):
        path = self.generator.generate_from_dict({
            'type': 'gradient', 'color': '#FF0000',
            'text_color': '#0000FF', 'size': [19, 20],
        })
        with Image.open(path) as image:
            self.assertEqual(image.size, (19, 20))
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
            middle = image.getpixel((0, 10))
            self.assertTrue(120 <= middle[0] <= 135)
            self.assertEqual(middle[1], 0)
            self.assertTrue(120 <= middle[2] <= 135)
            bottom = image.getpixel((0, 19))
            self.assertLess(bottom[0], 20)
            self.assertEqual(bottom[1], 0)
            self.assertGreater(bottom[2], 235)
            for y in range(image.height):
                self.assertEqual(image.getpixel((0, y)),
                                 image.getpixel((image.width - 1, y)))

    def test_text_icons_show_centered_foreground_on_requested_background(self):
        for text in ('REC', 'REC\nNOW'):
            with self.subTest(text=text):
                path = self.generator.generate_from_dict({
                    'type': 'text', 'color': '#102030', 'text': text,
                    'text_color': '#FFFFFF', 'font_size': 30, 'size': [180, 120],
                })
                with Image.open(path) as image:
                    self.assertEqual(image.size, (180, 120))
                    self.assertEqual(image.getpixel((0, 0)), (16, 32, 48))
                    background = Image.new('RGB', image.size, '#102030')
                    bounds = ImageChops.difference(image, background).getbbox()
                    self.assertIsNotNone(bounds)
                    left, top, right, bottom = bounds
                    self.assertGreater(left, 0)
                    self.assertGreater(top, 0)
                    self.assertLess(right, image.width)
                    self.assertLess(bottom, image.height)
                    self.assertAlmostEqual((left + right) / 2, image.width / 2, delta=12)
                    self.assertAlmostEqual((top + bottom) / 2, image.height / 2, delta=12)
                    self.assertIn((255, 255, 255), image.getdata())


if __name__ == '__main__':
    unittest.main()
