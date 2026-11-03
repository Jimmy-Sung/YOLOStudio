import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='nt','Windows GPU selector')
class GpuSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        subprocess.run([str(compiler),'/nologo','/target:exe','/platform:x64','/main:GpuDetect','/out:'+str(cls.root/'GpuDetect.exe'),'/reference:System.Web.Extensions.dll',str(ROOT/'gpu_selector.cs')],check=True,capture_output=True)
        cls.catalog=cls.root/'catalog.json';cls.catalog.write_text(json.dumps({'profiles':[
            {'id':'cu126','label':'CUDA 12.6','python':'engines/cu126/pythonw.exe','min_driver_api':12060,'priority':126,'archs':[50,60,70,75,80,86,90]},
            {'id':'cu128','label':'CUDA 12.8','python':'engines/cu128/pythonw.exe','min_driver_api':12080,'priority':128,'archs':[75,80,86,90,100,120]},
        ]}))

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def select(self,driver,capabilities,installed=False):
        fixture=self.root/'fixture.json';fixture.write_text(json.dumps({'driver_api':driver,'gpus':[{'index':i,'name':'GPU '+str(cap),'capability':cap} for i,cap in enumerate(capabilities)]}))
        args=[str(self.root/'GpuDetect.exe'),'--catalog',str(self.catalog),'--fixture',str(fixture),'--root',str(self.root)]
        if not installed:args.append('--allow-uninstalled')
        return json.loads(subprocess.check_output(args).decode('utf-8-sig'))

    def test_model_capability_and_driver_choose_runtime(self):
        for driver,caps,expected in [(13030,[86],'cu128'),(12060,[86],'cu126'),(13030,[61],'cu126'),(12080,[120],'cu128'),(12060,[120],'cpu'),(12040,[86],'cpu'),(13030,[35],'cpu'),(0,[],'cpu')]:
            with self.subTest(driver=driver,capabilities=caps):self.assertEqual(self.select(driver,caps)['id'],expected)

    def test_multi_gpu_selects_a_compatible_device(self):
        selected=self.select(13030,[61,120]);self.assertEqual(selected['id'],'cu128');self.assertEqual(selected['gpu_index'],1)

    def test_missing_runtime_does_not_launch_a_nonexistent_interpreter(self):
        self.assertEqual(self.select(13030,[86],installed=True)['id'],'cpu')
