"""Evidence-only OCR recovery. No workbook lookup, field guessing, or DB access."""
import re
from collections import defaultdict
from datetime import date, datetime
from .mrz import digit
from .fields import normalize

NUMERIC = str.maketrans({'O':'0','I':'1','S':'5','B':'8','Z':'2'})
CRITICAL = ('passport_number','dob','gender','date_of_issue','date_of_expiry')
DATE_RE = r'(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})'


def canonical(field, value):
    try:
        value = normalize(field, value)
        if field == 'full_name' and not re.fullmatch(r"[A-Z][A-Z '-]{1,100}", value):
            return ''
        if field == 'nationality' and not re.fullmatch('[A-Z]{3}', value):
            return ''
        return value
    except (ValueError, TypeError):
        return ''


def date_value(raw, birth=False):
    raw = raw.translate(NUMERIC)
    if not re.fullmatch(r'\d{6}', raw):
        return ''
    year = 2000 + int(raw[:2])
    if birth and year > date.today().year:
        year -= 100
    try:
        return datetime.strptime(str(year) + raw[2:], '%Y%m%d').date().isoformat()
    except ValueError:
        return ''


def checked_prefix(line):
    """Recover checksummed fields only; optional-data/filler damage is irrelevant.

    This deliberately does not insert/delete characters in protected positions.
    Character correction is numeric-position specific and must pass its check digit.
    """
    line = re.sub(r'\s+', '', line.upper())
    if len(line) < 28 or not re.fullmatch('[A-Z0-9<]+', line):
        return None
    country = line[10:13]
    if not re.fullmatch('[A-Z]{3}', country):
        return None
    p = line[:9]
    if country == 'IND' and p.endswith('<'):
        lead = {'8':'B','0':'O','5':'S','2':'Z','1':'I'}.get(p[0], p[0])
        p = lead + p[1:8].translate(NUMERIC) + '<'
        if not re.fullmatch('[A-Z]{1,2}[0-9]{6,7}<', p):
            return None
    if digit(p) != line[9].translate(NUMERIC):
        return None
    birth, expiry = line[13:19].translate(NUMERIC), line[21:27].translate(NUMERIC)
    if not re.fullmatch(r'\d{6}', birth) or not re.fullmatch(r'\d{6}', expiry):
        return None
    if digit(birth) != line[19].translate(NUMERIC) or digit(expiry) != line[27].translate(NUMERIC):
        return None
    dob, end = date_value(birth, True), date_value(expiry)
    if not dob or not end or dob >= end or line[20] not in 'MFX<':
        return None
    return {'passport_number':p.rstrip('<'),'dob':dob,'date_of_expiry':end,
            'gender':line[20].replace('<','X'),'nationality':country}


def mrz_name(line):
    line = re.sub(r'\s+', '', line.upper())
    if not re.match(r'^P<[A-Z]{3}', line):
        return ''
    part = line[5:]
    if '<<' not in part:
        return ''
    surname, given = part.split('<<', 1)
    # Only an explicit filler run terminates the given-name field. Never trim
    # arbitrary trailing letters to make a name look plausible.
    if '<<' not in given:
        return ''
    given = given.split('<<',1)[0]
    name = ' '.join((given.replace('<',' ')+' '+surname.replace('<',' ')).split())
    return canonical('full_name', name)


def printed_candidates(text):
    """Read split label tokens without combining values from different passes."""
    lines = [x.strip() for x in text.upper().splitlines() if x.strip()]
    found = defaultdict(set)
    # These aliases are restricted to anchored labels; they are not name/date
    # character substitution rules and cannot use Excel to change a value.
    labels = {
        'passport_number': r'PASSPORT\s*(?:NUMBER|NO\.?)',
        'full_name': r'(?:FULL\s*NAME|GIVEN\s*NAMES?)',
        'gender': r'(?:SEX|GENDER)',
        'nationality': r'NATIONALITY',
        'dob': r'(?:DATE|OATE|GATE)\s*(?:OF|0F)\s*BIRTH',
        'date_of_issue': r'(?:[A-Z0-9/._-]{0,12}\s*)?(?:(?:DATE|OATE|GATE)\s*(?:OF|0F)?\s*)?(?:ISSUE|[IL1]SSUE|ISSUC)',
        'date_of_expiry': r'(?:(?:DATE|OATE|GATE)\s*(?:OF|0F)\s*)?EXPIRY',
    }
    for i in range(len(lines)):
        # OCR often emits 'Full', 'Name', 'TEST PERSON' as three boxes.
        for n in (1,2,3):
            label = ' '.join(lines[i:i+n])
            for field, pattern in labels.items():
                match = re.fullmatch(pattern+r'\s*[:=._-]*\s*(.*)',label)
                if not match:
                    continue
                value = match.group(1).strip()
                if not value and i+n < len(lines):
                    value = lines[i+n]
                if field in ('dob','date_of_issue','date_of_expiry'):
                    d = re.fullmatch(DATE_RE,value)
                    value = ('%s-%s-%s' % (d[3], d[2].zfill(2), d[1].zfill(2))) if d else ''
                elif field == 'passport_number':
                    value = re.sub(r'\s+','',value)
                    if not re.fullmatch('[A-Z0-9]{5,15}',value):
                        value = ''
                # A given name alone is only a display candidate. Approval
                # needs independent MRZ/full-name evidence below.
                value = canonical(field,value)
                if value:
                    found[field].add(value)
    return found


def reconcile(result):
    """Re-resolve critical fields from raw evidence, retaining review reasons.

    full_name has no MRZ check digit; repeated agreement is required for confidence.
    An MRZ prefix check does not validate the optional/composite part of a full MRZ.
    """
    votes = {field:defaultdict(set) for field in list(CRITICAL) + ['full_name', 'nationality']}
    protected = {field:set() for field in CRITICAL}
    prefixes = []
    mrz_names = defaultdict(set)
    for page_index, evidence in enumerate(result.get('evidence',[])):
        for engine, key in [('tesseract','tesseract_text'),('easyocr','easyocr_text'),('mrz','mrz_text')]:
            text = evidence.get(key,'') or ''
            # Dedicated Tesseract MRZ is not counted as an independent engine.
            voter = (page_index, 'tesseract' if engine == 'mrz' else engine)
            if engine != 'mrz':
                for field, values in printed_candidates(text).items():
                    for value in values:
                        votes[field][value].add(voter)
            for line in text.splitlines():
                prefix = checked_prefix(line)
                if prefix:
                    prefixes.append(prefix)
                    for field,value in prefix.items():
                        if field in ('passport_number', 'dob', 'date_of_expiry'):
                            protected[field].add(value)
                        else:
                            votes[field][value].add(voter)
                name = mrz_name(line)
                if name:
                    mrz_names[name].add(voter)
                    votes['full_name'][name].add(voter)
    issues=[]
    quality={}
    for field in CRITICAL:
        checked = protected[field]
        options = votes[field]
        # Preserve an earlier conservative parser recovery for display when the
        # resolver cannot independently confirm it. It still remains untrusted.
        try:
            existing = canonical(field, (result.get('fields') or {}).get(field,''))
        except Exception:
            existing = ''
        choice = ''
        trusted = False
        source = 'missing'
        if len(checked) == 1:
            choice = next(iter(checked))
            trusted = True
            source = 'MRZ prefix with passport/DOB/expiry checks'
        elif len(checked) > 1:
            choice = existing if existing in checked else sorted(checked)[0]
            issues.append('Conflicting checked MRZ values: '+field)
            source = 'conflicting MRZ evidence'
        elif options:
            ranked = sorted(options, key=lambda v:(-len(options[v]),v))
            top = ranked[0]
            tied = len(ranked)>1 and len(options[top])==len(options[ranked[1]])
            if not tied:
                choice=top
                trusted=len(options[top])>=2 and (len(ranked)==1 or len(options[top])>len(options[ranked[1]]))
                source='OCR consensus' if trusted else 'provisional OCR candidate'
            else:
                choice = existing if existing in options else ''
                issues.append('Unresolved OCR disagreement: '+field)
                source='conflicting OCR evidence'
        elif existing:
            choice = existing
            source = 'provisional parser candidate'
        if not choice:
            issues.append('Missing or ambiguous OCR value: '+field)
        elif not trusted:
            issues.append('Independent confirmation required: '+field)
        result['fields'][field]=choice
        quality[field]={'trusted':trusted,'source':source}
    # Resolve full_name: display-only, not an approval field, but needs evidence.
    display_warnings = []
    for field in ('full_name', 'nationality'):
        options = votes[field]
        try:
            existing = canonical(field, (result.get('fields') or {}).get(field, ''))
        except Exception:
            existing = ''
        choice = ''
        trusted = False
        source = 'missing'
        if options:
            ranked = sorted(options, key=lambda v: (-len(options[v]), v))
            top = ranked[0]
            tied = len(ranked) > 1 and len(options[top]) == len(options[ranked[1]])
            if not tied:
                choice = top
                trusted = len(options[top]) >= 2
                source = 'OCR consensus' if trusted else 'provisional OCR candidate'
            else:
                # Tied: prefer existing if it's among the options, otherwise leave empty.
                choice = existing if existing in options else ''
                display_warnings.append('Unresolved OCR disagreement: ' + field)
                source = 'conflicting OCR evidence'
        # Do NOT fall back to an old parser value with no evidence.
        if not choice:
            display_warnings.append('Missing or ambiguous OCR value: ' + field)
        result['fields'][field] = choice
        quality[field] = {'trusted': trusted, 'source': source}
    identities={p['passport_number'] for p in prefixes}
    # Ignore differing filler/optional-data OCR variants as extra identities.
    result['multiple_identities']=len(identities)>1
    if result['multiple_identities']:
        issues.append('Multiple checked passport numbers found.')
    result['ocr_quality']={'version':1,'fields':quality,'review_required':bool(issues),'reasons':issues}
    # Keep original evidence/warnings for traceability, distinguish resolved display.
    result['warnings']=list(dict.fromkeys(result.get('warnings',[])+[
        'Critical fields were re-resolved from OCR evidence; see ocr_quality.']+issues+display_warnings))
    return result
