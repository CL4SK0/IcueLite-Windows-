import json
import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from icuelite import render


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = render.DEVICE_ART
        render.DEVICE_ART = self.dir.name
        render._photos.clear()
        render._cache.clear()
        img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle((10, 10, 190, 90), fill=(30, 30, 32, 255))
        img.save(os.path.join(self.dir.name, "k100.png"))
        zone = Image.new("L", (200, 100), 0)
        ImageDraw.Draw(zone).rectangle((20, 40, 180, 80), fill=255)
        zone.save(os.path.join(self.dir.name, "k100_touches.png"))
        with open(os.path.join(self.dir.name, "k100.json"), "w", encoding="utf-8") as f:
            json.dump({"zones": {"Touches": "k100_touches.png"}, "colors": {"Touches": [255, 212, 0]},
                       "logo": [100, 25, 20]}, f)

    def tearDown(self):
        render.DEVICE_ART = self.old
        render._photos.clear()
        render._cache.clear()
        self.dir.cleanup()

    def test_no_photo(self):
        self.assertIsNone(render.compose("ironclaw", 100, 50))
        self.assertEqual(render.zones("ironclaw"), [])

    def test_zone_colors(self):
        self.assertEqual(render.zones("k100"), ["Touches"])
        center = (200, 120)  # milieu de la zone lumineuse, cadre 400 × 200
        lit = render.compose("k100", 400, 200).getpixel(center)
        red = render.compose("k100", 400, 200, {"Touches": (255, 0, 0)}).getpixel(center)
        off = render.compose("k100", 400, 200, {"Touches": None}).getpixel(center)
        self.assertGreater(lit[1], 150)                    # jaune d'origine
        self.assertGreater(red[0], 200)
        self.assertLess(red[1], 60)
        self.assertLess(max(off[:3]), 60)                  # éteint : le plastique sombre


if __name__ == "__main__":
    unittest.main()
