from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'frontend-qt'))
from nspb_qt.win.build_app import stage_lan_control
class ControlPackagingTest(unittest.TestCase):
 def test_game_control_is_staged_without_modifying_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'original.nacp';dst=root/'dm';dst.mkdir()
   original=bytes(range(256))*64;src.write_bytes(original)
   stage_lan_control(src,dst)
   self.assertEqual((dst/'control.nacp').read_bytes(),original)
   self.assertEqual(src.read_bytes(),original)
 def test_missing_control_does_not_create_fake_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);stage_lan_control(root/'absent',root)
   self.assertFalse((root/'control.nacp').exists())
if __name__=='__main__':unittest.main()
