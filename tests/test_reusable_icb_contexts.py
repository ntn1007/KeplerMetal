"""Receipt falsification tests; no GPU work and no simulated hardware claim."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_command_ir_dataflow import verify_reusable_lease_receipts


def receipts(mode='basic'):
 phases=(['producer_reserved']if mode!='no_producer'else[])+['materializer_recording']+(['consumer_after_completed_materializer'if mode=='delayed_consumer'else'consumer_recording']if mode!='no_consumer'else[])
 return [dict(generation=i+1,GPU_addresses=dict(producerContext=0x500001000),intermediate_CPU_waits=int(mode=='delayed_consumer'),
  stale_plan_error='Command IR argument plan is inactive'if i else'',
  retired_mutation_error='GPU-selected command requires reset before CPU re-encoding',retired_consumer_error='Reusable consumer generation is not materialized/active',
  lease_checks=[dict(phase=p,PASS=True,prepare_refused=True,reset_refused=True,
   prepare_error='Reusable context still has uncompleted submissions',reset_error='Reusable context still has uncompleted submissions',
   materializer_status=4 if p=='consumer_after_completed_materializer'else 0)for p in phases])for i in range(4)]


class ReusableContextReceipts(unittest.TestCase):
 def test_all_phases_and_delayed_consumer_have_distinct_requirements(self):
  for mode,count in [('basic',24),('no_producer',16),('no_consumer',16),('delayed_consumer',24)]:
   proof=verify_reusable_lease_receipts(receipts(mode),mode)
   self.assertEqual(proof['lease_refusals'],count);self.assertEqual(proof['stale_CPU_plans_refused'],3)
 def test_generation_and_physical_buffer_reuse_are_both_required(self):
  for value in [0,0x1000000,1]:
   data=receipts();data[1]['generation']=value
   with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')
  data=receipts();data[1]['GPU_addresses']['producerContext']+=512
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')
 def test_success_boolean_does_not_replace_two_explicit_refusals(self):
  for field,value in [('prepare_refused',False),('reset_refused',False),('prepare_error','unrelated failure'),('reset_error','unrelated failure')]:
   data=receipts();data[2]['lease_checks'][1][field]=value
   with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')
 def test_missing_consumer_tracking_is_rejected(self):
  data=receipts();data[1]['lease_checks'].pop()
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')
 def test_completed_materializer_does_not_mean_idle_context(self):
  data=receipts('delayed_consumer');data[1]['lease_checks'][-1]['materializer_status']=0
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'delayed_consumer')
  data=receipts('delayed_consumer');data[1]['intermediate_CPU_waits']=0
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'delayed_consumer')
 def test_rejected_mutation_cannot_detach_a_retired_slot(self):
  data=receipts();data[2]['retired_consumer_error']=''
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')
 def test_stale_cpu_plan_must_be_refused_after_each_reset(self):
  data=receipts();data[3]['stale_plan_error']=''
  with self.assertRaises(AssertionError):verify_reusable_lease_receipts(data,'basic')

if __name__=='__main__':unittest.main()
