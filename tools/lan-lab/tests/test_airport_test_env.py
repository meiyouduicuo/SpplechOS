import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('airport_test_env',Path(__file__).resolve().parents[1]/'airport_test_env.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AirportEnvironmentTests(unittest.TestCase):
    def test_fresh_test_app_enables_lan_without_a_documents_file(self):
        result=module.with_lan_defaults('DM_ACNH_AIRPORT_TEST=1\n')
        self.assertIn('DM_LAN=1\n',result)
        self.assertIn('DM_LDN_TRACE=1\n',result)
        self.assertIn('DM_ACNH_AIRPORT_TEST=1\n',result)

    def test_repeated_packaging_does_not_add_duplicate_settings(self):
        first=module.with_lan_defaults('DM_ACNH_AIRPORT_TEST=1')
        self.assertEqual(module.with_lan_defaults(first),first)

    def test_explicit_settings_are_preserved(self):
        text='DM_LAN = 0\nDM_LDN_TRACE=0\n'
        self.assertEqual(module.with_lan_defaults(text),text)
