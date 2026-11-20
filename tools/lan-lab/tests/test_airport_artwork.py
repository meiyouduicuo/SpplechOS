import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('airport_artwork',Path(__file__).resolve().parents[1]/'airport_artwork.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class AirportArtworkTests(unittest.TestCase):
    def test_cached_banner_is_selected_before_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cached=root/'01006F8002326000.jpg';cached.write_bytes(b'cached banner')
            self.assertEqual(module.select_banner(root/'framework',cached_paths=[None,cached]),cached)

    def test_existing_framework_banner_is_available_without_desktop_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);banner=root/'banner.png';banner.write_bytes(b'existing banner')
            self.assertEqual(module.select_banner(root),banner)
            self.assertEqual(banner.read_bytes(),b'existing banner')

    def test_explicit_choice_has_priority_and_invalid_choice_is_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);selected=root/'selected.jpg';selected.write_bytes(b'chosen')
            cached=root/'cached.png';cached.write_bytes(b'cached')
            self.assertEqual(module.select_banner(root,selected,[cached]),selected)
            with self.assertRaises(ValueError):module.select_banner(root,root/'missing.jpg',[cached])

    def test_missing_optional_artwork_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertIsNone(module.select_banner(Path(tmp)))
