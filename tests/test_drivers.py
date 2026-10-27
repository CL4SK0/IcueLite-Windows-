import unittest

from icuelite.drivers import bragi, hydro, legacy, link
from icuelite.drivers.base import DriverError, pick_interface


class FakeTransport:
    def __init__(self, output_len=65, replies=()):
        self.output_len = output_len
        self.sent = []
        self.replies = list(replies)

    def write(self, data):
        assert len(data) == self.output_len, (len(data), self.output_len)
        self.sent.append(bytes(data))

    def read(self, timeout_ms=500):
        return self.replies.pop(0) if self.replies else b""

    def close(self):
        pass


class LegacyTest(unittest.TestCase):
    def test_colors_switch_to_software_mode_first(self):
        t = FakeTransport()
        d = legacy.Ironclaw(t)
        d.set_colors({"Logo": (255, 0, 0), "Molette": None}, brightness=50)
        self.assertEqual(t.sent[0][:4], b"\x00\x07\x04\x02")
        self.assertEqual(t.sent[1][:5], bytes([0, 0x07, 0x22, 3, 0x01]))
        # Logo (zone 2) à moitié de rouge, molette (zone 4) éteinte
        self.assertIn(bytes([2, 128, 0, 0]), t.sent[1])
        self.assertIn(bytes([4, 0, 0, 0]), t.sent[1])
        d.close()
        self.assertEqual(t.sent[-1][:4], b"\x00\x07\x04\x01")  # rend la main en partant

    def test_dpi(self):
        t = FakeTransport()
        stages = legacy.Ironclaw(t).set_dpi([800, 1625, 99999], 1)
        self.assertEqual(stages, [800, 1600, 18000])
        self.assertEqual(t.sent[0][:10], bytes([0, 0x07, 0x13, 0xD1, 0, 0, 0x20, 0x03, 0x20, 0x03]))
        self.assertEqual(t.sent[3][:6], bytes([0, 0x07, 0x13, 0x05, 0, 0b1110]))
        self.assertEqual(t.sent[4][:6], bytes([0, 0x07, 0x13, 0x02, 0, 2]))

    def test_poll(self):
        t = FakeTransport()
        legacy.Ironclaw(t).set_poll_rate(500)
        self.assertEqual(t.sent[0][:6], bytes([0, 0x07, 0x0A, 0, 0, 2]))
        with self.assertRaises(DriverError):
            legacy.Ironclaw(t).set_poll_rate(333)


class BragiTest(unittest.TestCase):
    def test_planar_and_chunks(self):
        self.assertEqual(bragi.planar([(1, 2, 3), (4, 5, 6)]), bytes([1, 4, 2, 5, 3, 6]))
        packets = bragi.write_resource(64, 0, bytes(range(200)))
        self.assertEqual(packets[0][:8], bytes([0, 0x08, 0x06, 0x00, 200, 0, 0, 0]))
        self.assertEqual(packets[1][:4], bytes([0, 0x08, 0x07, 0x00]))
        data = packets[0][8:] + b"".join(p[4:] for p in packets[1:])
        self.assertEqual(data[:200], bytes(range(200)))

    def test_k100_colors(self):
        t = FakeTransport()
        d = bragi.K100(t)
        d.set_colors({"Touches": (10, 20, 30)}, brightness=40)
        self.assertEqual(t.sent[0][:6], bytes([0, 0x08, 0x01, 0x03, 0x00, 0x02]))  # mode logiciel
        self.assertIn(bytes([0, 0x08, 0x0D, 0x00, 0x01]), [p[:5] for p in t.sent])  # ouverture de l'éclairage
        self.assertIn(bytes([0, 0x08, 0x01, 0x02, 0x00, 0x90, 0x01]), [p[:7] for p in t.sent])  # 400/1000


class LinkTest(unittest.TestCase):
    def test_parse_channels(self):
        reply = bytes([0, 0, 0x08, 0, 0x25, 0x00, 3, 0, 0xE8, 0x03, 1, 0, 0, 0, 0xDC, 0x05]) + bytes(20)
        self.assertEqual(link.parse_channels(reply, link.TYPE_SPEEDS), [(0, 1000), (2, 1500)])
        self.assertEqual(link.parse_channels(reply, link.TYPE_TEMPS), [])

    def test_fan_duty_has_a_floor(self):
        speeds = bytes([0, 0, 0x08, 0, 0x25, 0x00, 2, 0, 0xE8, 0x03, 0, 0xE8, 0x03]) + bytes(20)
        t = FakeTransport(output_len=513, replies=[b"", b"", speeds, b"", b"", b"", b"", b""])
        d = link.LinkHub(t)
        d.read_sensors()
        d.set_fan_duty(5)
        self.assertEqual(d.duty, link.MIN_DUTY)
        write = next(p for p in t.sent if p[3:5] == b"\x06\x01")
        self.assertEqual(write[9:11], link.TYPE_SET_SPEED)
        self.assertEqual(write[11:20], bytes([2, 0, 0, 20, 0, 1, 0, 20, 0]))


class InterfaceTest(unittest.TestCase):
    def test_pick_vendor_interface(self):
        infos = [{"usage_page": 0x0001, "output_report_length": 0, "interface_number": 0},
                 {"usage_page": 0xFFC2, "output_report_length": 65, "interface_number": 1, "path": "x"}]
        self.assertEqual(pick_interface(infos, (0xFFC2,), 64)["path"], "x")
        with self.assertRaises(DriverError):
            pick_interface(infos[:1])


if __name__ == "__main__":
    unittest.main()


class HydroTest(unittest.TestCase):
    def reply(self, body):
        r = bytearray(64)
        r[:len(body)] = body
        r[-1] = hydro.crc8(r[1:-1])
        return bytes(r)

    def test_crc_and_packet(self):
        self.assertEqual(hydro.crc8(b"123456789"), 0xF4)  # valeur de contrôle du CRC-8 SMBus
        p = hydro.packet(3, hydro.FEATURE_COOLING, hydro.CMD_STATUS)
        self.assertEqual(p[:4], bytes([0, 0x3F, 3 << 3, 0xFF]))
        self.assertEqual(hydro.crc8(p[2:]), 0)
        light = hydro.packet(1, None, 0b101, b"\x01\x02")
        self.assertEqual(light[2:5], bytes([(1 << 3) | 0b101, 1, 2]))

    def test_status(self):
        body = bytearray(31)
        body[0] = 0xFF
        body[2], body[3] = 0x12, 7
        body[7], body[8] = 128, 30
        body[15:17] = (900).to_bytes(2, "little")
        body[22:24] = (950).to_bytes(2, "little")
        body[29:31] = (2400).to_bytes(2, "little")
        st = hydro.parse_status(self.reply(body))
        self.assertEqual(st["firmware"], "1.2.7")
        self.assertAlmostEqual(st["liquid"], 30.5, places=1)
        self.assertEqual((st["fans"], st["pump"]), ([900, 950], 2400))
        self.assertIsNone(hydro.parse_status(bytes(64)[:-1] + b"\x01"))

    def test_real_reply_with_odd_crc(self):
        # réponse de l'H150i Elite d'un testeur (CRC différent de celui attendu)
        head = bytes.fromhex("ff381208 00724e4e 200f02ff b80bff0d 0702ffb8 0bffee")
        st = hydro.parse_status(head + bytes(64 - len(head)))
        self.assertEqual(st["firmware"], "1.2.8")
        self.assertAlmostEqual(st["liquid"], 32.3, places=1)
        self.assertEqual(st["fans"][0], 0x070D)

    def test_fixed_duty_and_floor(self):
        t = FakeTransport()
        d = hydro.Hydro(t)
        d.set_fan_duty(10)
        self.assertEqual(d.duty, hydro.MIN_DUTY)
        data = t.sent[0][4:]
        self.assertEqual(t.sent[0][3], hydro.CMD_SET_COOLING)
        self.assertEqual(data[hydro.FAN_MODE[0]], hydro.MODE_FIXED)
        self.assertEqual(data[hydro.FAN_DUTY[1]], round(25 * 255 / 100))
        self.assertEqual(data[hydro.PUMP_MODE], 1)
        self.assertEqual(t.sent[1][2] & 0b111, hydro.FEATURE_COOLING2)  # 3e ventilateur


class ReconnectTest(unittest.TestCase):
    def test_bragi_firmware_and_reconnect(self):
        from icuelite.drivers import bragi

        class Gone(FakeTransport):
            def write(self, data):
                raise OSError(1167, "écriture : Le périphérique n'est pas connecté. (code 1167)")

        size = 1025
        reply = bytes.fromhex("0000020001 0f3d") + bytes(size - 7)
        fresh = FakeTransport(size, [reply])
        d = bragi.K100(Gone(size), {"path": "a"})
        d.reopen = lambda: (fresh, {"path": "b"})
        import icuelite.drivers.base as base
        sleep, base.time.sleep = base.time.sleep, lambda s: None
        try:
            self.assertEqual(d.firmware(), "1.15.61")
        finally:
            base.time.sleep = sleep
        self.assertIs(d.transport, fresh)
        self.assertEqual(d.interface["path"], "b")


class OptionsTest(unittest.TestCase):
    def test_ironclaw_options(self):
        t = FakeTransport()
        d = legacy.Ironclaw(t)
        d.set_option("snap", "Activée")
        d.set_option("lift", "Haute")
        self.assertEqual(t.sent[0][1:6], bytes([0x07, 0x13, 0x04, 0x00, 0x01]))
        self.assertEqual(t.sent[1][1:6], bytes([0x07, 0x13, 0x03, 0x00, 0x04]))

    def test_bragi_brightness_and_virtuoso_size(self):
        ack = bytes([0x00, 0x00, 0x01, 0x00]) + bytes(61)
        t = FakeTransport(64, [ack])
        d = bragi.VirtuosoXT(t)
        self.assertEqual(d.size, 63)
        d.set_option("brightness", "50 %")
        self.assertEqual(t.sent[0][:7], bytes([0x00, 0x08, 0x01, 0x02, 0x00, 0xF4, 0x01]))

    def test_hydro_curve(self):
        t = FakeTransport()
        d = hydro.Hydro(t)
        d.set_option("curve", "Performance")
        data = t.sent[0][4:]
        self.assertEqual(data[hydro.FAN_PROFILE[0] + 1], hydro.byte_of(45))
