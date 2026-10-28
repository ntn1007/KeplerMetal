import importlib.util,lzma,pathlib,struct,tempfile,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'bridge/tools/unpack_pbzx_checked.py'
s=importlib.util.spec_from_file_location('unpack_pbzx_checked',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def enc(n):return struct.pack('>Q',n)
def fixture():
 a=lzma.compress(b'compressed data');b=b'raw tail'
 return b'pbzx'+enc(0x1000000)+enc(0x1000000)+enc(len(a))+a+enc(0)+enc(len(b))+b
class PBZXTests(unittest.TestCase):
 def test_two_chunks(self):
  with tempfile.TemporaryDirectory() as d:
   src=pathlib.Path(d)/'p';out=pathlib.Path(d)/'out';src.write_bytes(fixture());r=m.unpack(src,out)
   self.assertEqual(out.read_bytes(),b'compressed dataraw tail');self.assertEqual(r['chunks'],2)
   with self.assertRaises(FileExistsError):m.unpack(src,out)
 def test_reject_truncated_and_trailing(self):
  for blob in [fixture()[:-1],fixture()+b'x',b'NOPE'+fixture()[4:]]:
   with tempfile.TemporaryDirectory() as d:
    src=pathlib.Path(d)/'p';src.write_bytes(blob)
    with self.assertRaises(ValueError):m.unpack(src,pathlib.Path(d)/'out')
