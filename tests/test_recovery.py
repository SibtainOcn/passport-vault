import os
import copy
import importlib.util
import json
import pathlib
import sys
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parent
pkg = types.ModuleType('candidate_vault')
pkg.__path__ = [str(pathlib.Path(os.environ.get('PV_TEST_ROOT',HERE.parent/'files'))/'vault')]
sys.modules['candidate_vault'] = pkg
from candidate_vault.ocr_recovery import reconcile, checked_prefix, mrz_name, printed_candidates
from candidate_vault.fields import normalize
from candidate_vault.mrz import digit
CASES = json.loads((HERE/'recorded_dummy_cases.json').read_text())


def replay(case):
    return reconcile({'fields':{k:v['actual'] for k,v in case['fields'].items()},
                      'evidence':copy.deepcopy(case['evidence']), 'warnings':[]})


def prefix(p='B2345678', dob='000403', expiry='300604', sex='M'):
    p = p.ljust(9,'<')
    return p+digit(p)+'IND'+dob+digit(dob)+sex+expiry+digit(expiry)


class RecoveryTests(unittest.TestCase):
    def test_large_recorded_seven_fields(self):
        r=replay(CASES[0])
        for f,v in CASES[0]['fields'].items():
            self.assertEqual(normalize(f,r['fields'][f]),normalize(f,v['expected']))
        self.assertNotIn('CCEE',r['fields']['full_name'])

    def test_small_recorded_seven_fields(self):
        r=replay(CASES[1])
        for f,v in CASES[1]['fields'].items():
            self.assertEqual(normalize(f,r['fields'][f]),normalize(f,v['expected']))

    def test_prefix_without_optional_data(self):
        self.assertEqual(checked_prefix(prefix())['passport_number'],'B2345678')

    def test_numeric_confusion_with_valid_check(self):
        self.assertEqual(checked_prefix(prefix().replace('B234','8234',1))['passport_number'],'B2345678')

    def test_bad_check_rejected(self):
        p=prefix();self.assertIsNone(checked_prefix(p[:9]+str((int(p[9])+1)%10)+p[10:]))

    def test_missing_protected_character_rejected(self):
        p=prefix();self.assertIsNone(checked_prefix(p[:4]+p[5:]))

    def test_impossible_date_rejected(self):
        self.assertIsNone(checked_prefix(prefix(dob='000231')))

    def test_incomplete_name_not_assumed_complete(self):
        self.assertEqual(mrz_name('P<IND<<TEST<PER'), '')

    def test_name_filler_noise_not_appended(self):
        self.assertEqual(mrz_name('P<IND<<TEST<PERSON<<<<CCCCCCCC'), 'TEST PERSON')

    def test_nonempty_surname(self):
        self.assertEqual(mrz_name('P<INDPERSON<<TEST<<<<'), 'TEST PERSON')

    def test_fragmented_date_label(self):
        r=printed_candidates('Date\nof\nIssue:\n05/06/2020')
        self.assertIn('2020-06-05',r['date_of_issue'])

    def test_invalid_printed_date_not_repaired(self):
        self.assertFalse(printed_candidates('Date of Issue: 05/66/2020')['date_of_issue'])

    def test_unresolved_names_are_review(self):
        r=reconcile({'fields':{},'evidence':[{'tesseract_text':'Full Name: ALPHA USER', 'easyocr_text':'Full Name: BETA USER'}]})
        self.assertEqual(r['fields']['full_name'],'')
        self.assertTrue(r['ocr_quality']['review_required'])

    def test_multiple_passports_block(self):
        r=reconcile({'fields':{},'evidence':[{'mrz_text':prefix()+'\n'+prefix('C3456789')}]})
        self.assertTrue(r['multiple_identities'])
        self.assertTrue(r['ocr_quality']['review_required'])

    def test_same_passport_different_filler_not_multiple(self):
        r=reconcile({'fields':{},'evidence':[{'mrz_text':prefix()+'<<<\n'+prefix()+'<<<<<<'}]})
        self.assertFalse(r['multiple_identities'])

    def test_gender_disagreement_not_protected_by_date_checks(self):
        r=reconcile({'fields':{},'evidence':[{'tesseract_text':prefix(sex='M'), 'easyocr_text':prefix(sex='F')}]})
        self.assertFalse(r['ocr_quality']['fields']['gender']['trusted'])
        self.assertEqual(r['fields']['gender'],'')

    def test_no_evidence_cannot_preserve_untrusted_old_name(self):
        r=reconcile({'fields':{'full_name':'CORRUPT OLD NAME'},'evidence':[]})
        self.assertEqual(r['fields']['full_name'],'')
        self.assertTrue(r['ocr_quality']['review_required'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
