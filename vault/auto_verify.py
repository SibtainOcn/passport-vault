from collections import defaultdict
from .fields import FIELDS, normalize
from .models import Workbook
from .crypto import unpack


def _active_master(owner):
    return Workbook.objects.filter(owner=owner, active=True).order_by('-created').first()


def _compare_document(owner, extracted_fields):
    """Compare OCR-extracted passport fields against the active master workbook.
    Returns a verification payload and one of approved/review/failed.
    """
    master = _active_master(owner)
    if not master:
        return {
            'status': 'review',
            'reason': 'No active Master Excel is configured. Upload and activate the master data first.',
            'comparisons': {},
            'master': None,
        }, 'review'

    cfg = master.config or {}
    sheets = unpack(master.data, 'workbook:'+str(master.id))
    sheet_name = cfg.get('sheet')
    header = cfg.get('header', 1)
    mapping = cfg.get('mapping') or {}
    date_format = cfg.get('date_format', 'DMY')
    if sheet_name not in sheets or not isinstance(header, int) or header < 1:
        return {'status':'review','reason':'Master Excel configuration is invalid. Reconfigure the master file.','comparisons':{},'master':str(master.id)}, 'review'
    approval_fields = {'passport_number','dob','gender','date_of_issue','date_of_expiry'}
    missing_mapping = sorted(approval_fields - set(mapping))
    if missing_mapping:
        return {'status':'review','reason':'Master Excel must map all five approval fields: Passport number, Date of birth, Gender, Date of issue and Date of expiry.','comparisons':{},'master':str(master.id)}, 'review'

    try:
        passport = normalize('passport_number', extracted_fields.get('passport_number',''))
    except ValueError:
        passport = ''
    if not passport:
        return {
            'status':'review',
            'reason':'Passport number could not be read confidently from the uploaded passport.',
            'comparisons':{}, 'master':str(master.id), 'master_name':master.name,
        }, 'review'

    candidates=[]
    rows=sheets[sheet_name]
    for row_num, values in enumerate(rows[header:], start=header+1):
        if not any(str(v).strip() for v in values):
            continue
        raw={f:(values[i] if i < len(values) else '') for f,i in mapping.items() if f in FIELDS and isinstance(i,int)}
        try:
            p=normalize('passport_number', raw.get('passport_number',''), date_format)
        except ValueError:
            p=''
        if p == passport:
            candidates.append((row_num,raw))

    if not candidates:
        return {
            'status':'failed',
            'reason':'Passport number was not found in the active Master Excel.',
            'passport_number':passport,
            'comparisons':{}, 'master':str(master.id), 'master_name':master.name,
        }, 'failed'
    if len(candidates) > 1:
        return {
            'status':'review',
            'reason':'More than one Master Excel row has this passport number. Resolve the duplicate.',
            'passport_number':passport,
            'comparisons':{}, 'master':str(master.id), 'master_name':master.name,
            'matches':[{'sheet':sheet_name,'row':r} for r,_ in candidates],
        }, 'review'

    row_num, raw = candidates[0]
    comparisons={}
    needs_review=False
    mismatches=[]
    for field, excel_value in raw.items():
        passport_value=extracted_fields.get(field,'')
        item={'excel':excel_value if excel_value is not None else '', 'passport':passport_value or ''}
        try:
            expected=normalize(field, excel_value, date_format)
        except ValueError:
            item['status']='Invalid Excel value'; needs_review=True; comparisons[field]=item; continue
        try:
            actual=normalize(field, passport_value, 'DMY') if passport_value else ''
        except ValueError:
            actual=''
        if not expected or not actual:
            item['status']='Missing value'; needs_review=True
        elif expected == actual:
            item['status']='Match'
        else:
            item['status']='Mismatch'; needs_review=True; mismatches.append(field)
        comparisons[field]=item

    if needs_review:
        reason = ('Fields differ: '+', '.join(mismatches)) if mismatches else 'One or more compared fields are missing or invalid.'
        state='review'; label='review'
    else:
        reason='All selected Master Excel fields match the passport OCR data.'
        state='approved'; label='approved'
    return {
        'status':label,
        'reason':reason,
        'passport_number':passport,
        'sheet':sheet_name,
        'row':row_num,
        'comparisons':comparisons,
        'master':str(master.id),
        'master_name':master.name,
    }, state


def verify_document(owner, extracted_fields, extraction=None):
    from .ocr_quality import apply_quality_gate
    verification, status = _compare_document(owner, extracted_fields)
    return apply_quality_gate(verification, status, extraction)
