"""CPU-only audit checks; synthetic data never becomes a video request."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
import video_reply_identity as a

def fixtures():
 old={'evidence_id':'ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9','subject':{'digest':{'sha256':a.IO_SHA}},'normalized_result':{'procedure':{'address':'0x9f70'},'assembly':list(a.VIDEO)}}
 records=[]
 for name,(eid,address,size,_) in a.CASES.items():
  records.append({'evidence_id':eid,'subject':{'digest':{'sha256':a.IO_SHA}},'normalized_result':{'procedure':{'address':hex(address),'body':{'available':True,'total_bytes':size}},'assembly':list(a.ANCHORS[name]),'callees':[{'address':'0x155600','name':'_panic'}] if name=='machine' else []}})
 return old,{'records':records}
class ReplyIdentityAudit(unittest.TestCase):
 def test_valid_fixture(self):a.validate_records(*fixtures())
 def test_modified_video_offset_is_refused(self):
  old,b=fixtures();old['normalized_result']['assembly'][2]='wrong';
  with self.assertRaises(ValueError):a.validate_records(old,b)
 def test_changed_shared_access_is_refused(self):
  old,b=fixtures();b['records'][0]['normalized_result']['assembly'][2]='wrong';
  with self.assertRaises(ValueError):a.validate_records(old,b)
 def test_changed_subject_is_refused(self):
  old,b=fixtures();b['records'][1]['subject']['digest']['sha256']='bad';
  with self.assertRaises(ValueError):a.validate_records(old,b)
 def test_duplicate_evidence_is_refused(self):
  old,b=fixtures();b['records'].append(copy.deepcopy(b['records'][0]));
  with self.assertRaises(ValueError):a.validate_records(old,b)
 def test_missing_panic_target_is_refused(self):
  old,b=fixtures();next(r for r in b['records'] if r['evidence_id']==a.CASES['machine'][0])['normalized_result']['callees']=[]
  with self.assertRaises(ValueError):a.validate_records(old,b)
if __name__=='__main__':unittest.main()
