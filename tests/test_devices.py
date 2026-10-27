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


class OtherDetectionTest(unittest.TestCase):
    def test_psu_and_memory(self):
        mods = [{"part": "CMK64GX5M2B6000Z40", "capacity_gb": 32, "speed": 4800, "rated": 6000, "cl": 40}] * 2
        found, _ = devices.detect(raw=[hid(0x0C37, "H150iELITE")], usb=[(0x1C11, "USB\\VID_1B1C&PID_1C11\\X")],
                                  modules=mods)
        self.assertEqual(set(found), {"h150i", "ax1600i", "vengeance"})
        self.assertIn("EXPO", found["vengeance"].note)
        found, _ = devices.detect(raw=[], usb=[], modules=[{"part": "F5-6000J3038", "capacity_gb": 16}])
        self.assertEqual(found, {})
