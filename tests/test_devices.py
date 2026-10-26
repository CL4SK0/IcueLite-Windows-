import unittest

from icuelite import devices


def hid(pid, name=""):
    return {"product_id": pid, "product_string": name, "interface_number": 0, "usage_page": 0xFF42, "usage": 1}


class DevicesTest(unittest.TestCase):
    def test_match_by_pid(self):
        self.assertEqual(devices.match(hid(0x1B5D)).key, "ironclaw")
        self.assertEqual(devices.match(hid(0x0C3F)).key, "link")

    def test_match_by_name(self):
        self.assertEqual(devices.match(hid(0x2B00, "CORSAIR VANGUARD PRO 96")).key, "vanguard")
        self.assertEqual(devices.match(hid(0x0A00, "Corsair Virtuoso XT Wireless")).key, "virtuoso")

    def test_board_devices_never_match(self):
        # Le Nautilus et la mémoire ne sont pas en USB : aucune interface ne doit leur être attribuée
        for info in (hid(0x1234, "NAUTILUS"), hid(0x1234, "VENGEANCE")):
            self.assertIsNone(devices.match(info))

    def test_detect_groups_interfaces(self):
        found, unknown = devices.detect([hid(0x1B7C), hid(0x1B7C), hid(0x9999, "Autre")])
        self.assertEqual(len(found["k100"].interfaces), 2)
        self.assertEqual(found["k100"].pid, 0x1B7C)
        self.assertEqual(len(unknown), 1)


if __name__ == "__main__":
    unittest.main()
