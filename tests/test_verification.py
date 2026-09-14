import copy,json,os,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(os.environ.get('PV_TEST_ROOT',Path(__file__).resolve().parent.parent))
pkg=types.ModuleType('tested_vault');pkg.__path__=[str(ROOT/'vault')];sys.modules['tested_vault']=pkg
models=types.ModuleType('tested_vault.models');models.Workbook=object;sys.modules[models.__name__]=models
crypto=types.ModuleType('tested_vault.crypto');crypto.unpack=lambda data,aad:data;sys.modules[crypto.__name__]=crypto
from tested_vault.auto_verify import verify_document

FIELDS={'passport_number':'Z1234567','full_name':'TEST PERSON','dob':'2000-04-03','gender':'M','nationality':'IND','date_of_issue':'2020-06-05','date_of_expiry':'2030-06-04'}
QUALITY={'ocr_quality':{'version':1,'review_required':False,'reasons':[], 'fields':{f:{'trusted':True} for f in FIELDS}},'multiple_identities':False}
MASTER=types.SimpleNamespace(id='dummy-master',name='Synthetic Master',config={'sheet':'Test','header':1,'date_format':'DMY','mapping':{f:i for i,f in enumerate(FIELDS)}},data={'Test':[list(FIELDS),list(FIELDS.values())]})

class VerifyTests(unittest.TestCase):
 def verify(self,fields=None,quality=None,master=MASTER):
  with patch('tested_vault.auto_verify._active_master',return_value=master):
   return verify_document(None,fields if fields is not None else FIELDS,quality)
 def test_confident_match_approved(self):
  self.assertEqual(self.verify(quality=QUALITY)[1],'approved')
 def test_missing_quality_not_autoapproved(self):
  self.assertEqual(self.verify()[1],'review')
 def test_disagreement_with_matching_values_review(self):
  q=copy.deepcopy(QUALITY);q['ocr_quality']['fields']['date_of_issue']['trusted']=False
  self.assertEqual(self.verify(quality=q)[1],'review')
 def test_general_quality_review_blocks_approval(self):
  q=copy.deepcopy(QUALITY);q['ocr_quality']['review_required']=True
  self.assertEqual(self.verify(quality=q)[1],'review')
 def test_multiple_identities_block(self):
  q=copy.deepcopy(QUALITY);q['multiple_identities']=True
  self.assertEqual(self.verify(quality=q)[1],'review')
 def test_confident_not_found_failed(self):
  f=dict(FIELDS,passport_number='C3456789');self.assertEqual(self.verify(f,QUALITY)[1],'failed')
 def test_uncertain_not_found_review(self):
  f=dict(FIELDS,passport_number='C3456789');q=copy.deepcopy(QUALITY);q['ocr_quality']['fields']['passport_number']['trusted']=False
  self.assertEqual(self.verify(f,q)[1],'review')
 def test_legacy_not_found_review(self):
  self.assertEqual(self.verify(dict(FIELDS,passport_number='C3456789'))[1],'review')
 def test_mismatch_stays_review(self):
  self.assertEqual(self.verify(dict(FIELDS,full_name='DIFFERENT USER'),QUALITY)[1],'review')
 def test_missing_field_review(self):
  self.assertEqual(self.verify(dict(FIELDS,date_of_issue=''),QUALITY)[1],'review')
 def test_missing_master_review(self):
  self.assertEqual(self.verify(quality=QUALITY,master=None)[1],'review')
 def test_duplicate_master_review(self):
  m=copy.deepcopy(MASTER);m.data['Test'].append(list(FIELDS.values()))
  self.assertEqual(self.verify(quality=QUALITY,master=m)[1],'review')
 def test_comparison_values_remain_visible_when_quality_blocks(self):
  v,s=self.verify();self.assertEqual(s,'review');self.assertEqual(v['comparisons']['full_name']['excel'],'TEST PERSON')
 def test_gate_does_not_mutate_input_quality(self):
  original=copy.deepcopy(QUALITY);self.verify(quality=QUALITY);self.assertEqual(original,QUALITY)

if __name__=='__main__':unittest.main(verbosity=2)
