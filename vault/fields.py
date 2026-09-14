import re, unicodedata
from datetime import date, datetime
FIELDS = ['passport_number','full_name','dob','gender','nationality','issuing_country','place_of_birth','date_of_issue','date_of_expiry','place_of_issue','father_name','mother_name','spouse_name','address','mrz']
DATES = {'dob','date_of_issue','date_of_expiry'}
def normalize(field,value, date_format='DMY'):
    if value is None: return ''
    if isinstance(value,(date,datetime)): return value.strftime('%Y-%m-%d')
    value = unicodedata.normalize('NFKC',str(value)).strip()
    if not value: return ''
    if field in DATES:
        formats = ['%Y-%m-%d','%Y/%m/%d']
        formats += ['%d/%m/%Y','%d-%m-%Y','%d.%m.%Y'] if date_format=='DMY' else ['%m/%d/%Y','%m-%d-%Y','%m.%d.%Y']
        for fmt in formats:
            try: return datetime.strptime(value,fmt).strftime('%Y-%m-%d')
            except ValueError: pass
        raise ValueError('Invalid date; use the selected date format or YYYY-MM-DD.')
    value = re.sub(r'\s+',' ',value).upper()
    if field=='passport_number':
        if not re.fullmatch(r'[A-Z0-9]{5,15}',value): raise ValueError('Passport number must contain 5-15 letters/digits; no automatic character replacement.')
    if field=='gender':
        value = {'MALE':'M','FEMALE':'F','UNSPECIFIED':'X','<':'X'}.get(value,value)
        if value not in ('M','F','X'): raise ValueError('Gender must be M, F or X.')
    if field in ('issuing_country','nationality'):
        value = {'INDIA':'IND','INDIAN':'IND'}.get(value,value)
    return value

def validate_fields(data):
    if not isinstance(data,dict): raise ValueError('Invalid field values.')
    if any(len(str(v))>4000 for v in data.values()): raise ValueError('Field value is too long.')
    result = {f:normalize(f,data.get(f,'')) for f in FIELDS}
    if not result['passport_number']: raise ValueError('Passport number is required for approval.')
    if not result['full_name']: raise ValueError('Full name is required for approval.')
    if result['dob'] and result['dob']>date.today().isoformat(): raise ValueError('Date of birth cannot be in the future.')
    if result['date_of_issue'] and result['date_of_expiry'] and result['date_of_issue']>result['date_of_expiry']: raise ValueError('Issue date must not be after expiry.')
    return result
