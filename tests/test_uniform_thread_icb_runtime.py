# SPDX-License-Identifier: MIT
"""Exercise the actual compiled ICB method with a CPU-only forwarding subclass."""
import hashlib,json,os,platform,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class UniformThreadRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(platform.system()=='Darwin' and os.getenv('KEPLER_UNIFORM_ARCHIVE'),'requires explicitly provided fresh macOS archive')
    def test_real_method_forwards_uniform_and_refuses_partial(self):
        build=Path(os.environ['KEPLER_UNIFORM_ARCHIVE']).resolve();m=json.loads((build/'manifest.json').read_text());library=build/'libKeplerMetal.a'
        self.assertEqual(m['status'],'PASS');self.assertEqual(sha(library),m['static_library_SHA256'])
        for name,digest in m['source_SHA256'].items():
            self.assertEqual(sha(ROOT/'bridge/src'/name),digest);self.assertEqual(sha(build/'src'/name),digest)
        with tempfile.TemporaryDirectory() as t:
            exe=Path(t)/'contract';cmd=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',str(ROOT/'tests/uniform_thread_icb_contract.mm'),'-Wl,-all_load',str(library),'-framework','Metal','-framework','Foundation','-o',str(exe)]
            subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=60);result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=15)
            self.assertEqual(json.loads(result.stdout),{'status':'PASS','uniform_cases':2,'refusal_cases':9,'forwarded_calls':2,'GPU_execution':False})
if __name__=='__main__':unittest.main()
