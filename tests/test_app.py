import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("tkinter") and importlib.util.find_spec("customtkinter"),
                     "interface graphique non installée")
class AppImportTest(unittest.TestCase):
    def test_import(self):
        # Vérifie au moins que l'interface se charge (le build Windows a tkinter et customtkinter)
        from icuelite import app
        self.assertTrue(callable(app.run))


if __name__ == "__main__":
    unittest.main()
