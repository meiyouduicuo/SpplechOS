import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

LAB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('send_test_data', LAB / 'send_test_data.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AFC:
    def __init__(self, names=()):
        self.names = list(names); self.dirs=[]; self.writes=[]; self.renames=[]
    async def get_file_contents(self, path): return b'beacon'
    async def get_device_info(self): return {'FSFreeBytes': 1024**3}
    async def makedirs(self, path): self.dirs.append(path)
    async def listdir(self, path): return ['.shell-host.json'] if path == '/Documents' else self.names
    async def fopen(self, path, mode): self.writes.append([path, bytearray()]); return len(self.writes)-1
    async def fwrite(self, h, data): self.writes[h][1].extend(data)
    async def fclose(self, h): pass
    async def stat(self, path): return {'st_size':len(next(data for name,data in self.writes if name==path))}
    async def rename(self, src, dst): self.renames.append((src,dst));self.names.append('msl')
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass

class TestDelivery(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, names, expect_error=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fw=root/'framework';fw.mkdir();image=root/'romfs.img';image.write_bytes(b'raw')
            shader=root/'b-abc.img';shader.write_bytes(b'shader')
            (fw/'game.manifest.json').write_text(json.dumps({'title_id':module.TITLE,'chain':'b-abc','romfs_identity':'identity'}))
            meta=root/'meta.json';meta.write_text(json.dumps({'title_id':module.TITLE,'chain':'b-abc','lib_path':str(shader)}))
            args=types.SimpleNamespace(framework=fw,shader_meta=meta,image=image)
            afc=AFC(names);calls=[]
            class Device:
                async def close(self): calls.append('close')
            class House:
                @staticmethod
                async def create(device,bundle,documents_only): calls.append(('house',bundle,documents_only));return afc
            class Proxy:
                def __init__(self,lockdown): pass
                async def get_apps(self,application_type): return {module.BUNDLE:{'Entitlements':{'com.apple.developer.team-identifier':'TEAM'}}}
            async def connect(): return Device()
            async def upload(*args,**kwargs): calls.append('romfs')
            async def aoc(*args,**kwargs): calls.append('aoc')
            with patch('pymobiledevice3.lockdown.create_using_usbmux',connect), patch('pymobiledevice3.services.house_arrest.HouseArrestService',House), patch('pymobiledevice3.services.installation_proxy.InstallationProxyService',Proxy), patch.object(module,'matches_romfs_identity',return_value=True), patch.object(module,'check_host'), patch.object(module,'upload_romfs',upload), patch.object(module,'upload_aoc',aoc):
                if expect_error:
                    with self.assertRaisesRegex(RuntimeError,'refusing to replace'): await module.main(args)
                    self.assertNotIn('romfs',calls);self.assertEqual(afc.writes,[])
                else:
                    await module.main(args)
                    self.assertEqual(calls[-3:],['romfs','aoc','close'])
                    self.assertEqual(bytes(afc.writes[0][1]),b'shader')
                    self.assertEqual(afc.renames[0][1],'/Documents/games/'+module.TITLE+'/msl')
    async def test_existing_data_is_never_replaced(self): await self.run_case(['romfs.img'],True)
    async def test_shader_is_staged_for_test_bundle(self): await self.run_case([])

if __name__=='__main__': unittest.main()
