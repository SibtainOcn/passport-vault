"""Evidence-only OCR recovery. No workbook lookup, field guessing, or DB access."""
import re
from collections import defaultdict
from datetime import date, datetime
from .mrz import digit
from .fields import normalize

NUMERIC = str.maketrans({'O':'0','I':'1','S':'5','B':'8','Z':'2'})
CRITICAL = ('passport_number','dob','gender','date_of_issue','date_of_expiry')
DATE_RE = r'(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{2,4})'


def _recover_date_of_issue(evidence_list, known_dob, known_expiry):
    """Scan raw OCR text for date patterns to recover date_of_issue.

    The MRZ standard does NOT include date of issue; it only has DOB and
    expiry.  On Indian passports the issue and expiry dates are printed
    side-by-side, which often defeats the label parser.  This heuristic
    collects every DD/MM/YYYY-style date from the OCR evidence, removes
    dates that match the already-known DOB and expiry, and picks the most
    plausible issue date from the remainder.
    """
    seen = set()
    for ev in evidence_list:
        for key in ('tesseract_text', 'easyocr_text', 'mrz_text'):
            text = ev.get(key, '') or ''
            for m in re.finditer(DATE_RE, text):
                raw_d, raw_m, raw_y = m.groups()
                # Normalise two-digit year
                y = raw_y
                if len(y) == 2:
                    y = ('19' if int(y) > 40 else '20') + y
                try:
                    dt = date(int(y), int(raw_m), int(raw_d))
                except ValueError:
                    continue
                seen.add(dt.isoformat())

    # Also scan for YYYY-MM-DD already-normalised dates in the text
    for ev in evidence_list:
        for key in ('tesseract_text', 'easyocr_text'):
            text = ev.get(key, '') or ''
            for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', text):
                try:
                    dt = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    seen.add(dt.isoformat())
                except ValueError:
                    continue

    # Remove dates that match known DOB or expiry
    seen.discard(known_dob)
    seen.discard(known_expiry)

    # Filter to plausible issue dates
    today = date.today()
    candidates = []
    for iso in seen:
        try:
            dt = date.fromisoformat(iso)
        except ValueError:
            continue
        # Issue date must be in the past or today
        if dt > today:
            continue
        # Issue date must be after DOB (if known)
        if known_dob:
            try:
                if dt <= date.fromisoformat(known_dob):
                    continue
            except ValueError:
                pass
        # Issue date must be before expiry (if known)
        if known_expiry:
            try:
                if dt >= date.fromisoformat(known_expiry):
                    continue
            except ValueError:
                pass
        candidates.append(iso)

    if not candidates:
        return ''
    # Prefer the most recent plausible date (passport renewals => latest issue)
    return max(candidates)


def _recover_gender(evidence_list):
    """Scan raw OCR text for gender when MRZ and label parsers both miss it.

    Indian passports print gender as "Sex M" or "Sex MALE" near the DOB.
    If the formal label parser fails (e.g. OCR garbles the label or merges
    it with adjacent text), this heuristic looks for standalone M/F/MALE/
    FEMALE tokens near a Sex/Gender anchor, or extracts the gender character
    from a partially-readable MRZ second line even when checksums fail.
    """
    gender_votes = defaultdict(int)

    for ev in evidence_list:
        for key in ('tesseract_text', 'easyocr_text'):
            text = (ev.get(key, '') or '').upper()
            lines = [l.strip() for l in text.splitlines() if l.strip()]

            for i, line in enumerate(lines):
                # Pattern 1: "Sex M" or "Gender FEMALE" on the same line
                m = re.search(
                    r'(?:SEX|GENDER|S[E3]X)\s*[:/=._\-]*\s*(MALE|FEMALE|M|F)\b',
                    line
                )
                if m:
                    token = m.group(1)
                    g = {'MALE': 'M', 'FEMALE': 'F'}.get(token, token)
                    if g in ('M', 'F'):
                        gender_votes[g] += 2  # High confidence

                # Pattern 2: "Sex" on one line, value on the next
                if re.search(r'\b(?:SEX|GENDER|S[E3]X)\s*[:/=._\-]*\s*$', line):
                    if i + 1 < len(lines):
                        next_val = lines[i + 1].strip()
                        if next_val in ('M', 'F', 'MALE', 'FEMALE'):
                            g = {'MALE': 'M', 'FEMALE': 'F'}.get(next_val, next_val)
                            if g in ('M', 'F'):
                                gender_votes[g] += 2

                # Pattern 3: Standalone M or F adjacent to date-like text or
                # nationality (common on Indian passport layout)
                # e.g. "INDIAN  25/05/1982  M" or "M  INDIAN"
                m2 = re.search(
                    r'(?:INDIAN|IND)\s+.*\b(M|F)\b|\b(M|F)\b\s+.*(?:INDIAN|IND)',
                    line
                )
                if m2:
                    g = m2.group(1) or m2.group(2)
                    if g in ('M', 'F'):
                        gender_votes[g] += 1

            # Pattern 4: Extract gender from partial MRZ even when checksums fail
            for line in lines:
                stripped = re.sub(r'\s+', '', line)
                # Look for TD3 second-line structure containing gender at pos 20
                m3 = re.match(
                    r'[A-Z0-9<]{10}[A-Z]{3}\d{6}\d([MFX])\d{6}\d',
                    stripped
                )
                if m3:
                    g = m3.group(1)
                    if g in ('M', 'F'):
                        gender_votes[g] += 1

    if not gender_votes:
        return ''
    return max(gender_votes, key=gender_votes.get)


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

    # ── Fallback recovery for fields the label/MRZ parsers commonly miss ──
    # Collect already-known DOB and expiry for date_of_issue filtering.
    _known_dob = next(iter(protected['dob']), '') or next(iter(votes['dob']), '')
    _known_exp = next(iter(protected['date_of_expiry']), '') or next(iter(votes['date_of_expiry']), '')
    evidence_list = result.get('evidence', [])

    # Date of issue: not in MRZ, Indian passports print it side-by-side with
    # expiry which defeats the label parser.  Recover from raw date patterns.
    if not votes['date_of_issue']:
        doi = _recover_date_of_issue(evidence_list, _known_dob, _known_exp)
        if doi:
            votes['date_of_issue'][doi].add(('fallback', 'date_scan'))

    # Gender: in MRZ but lost when the full MRZ line is too garbled for
    # checked_prefix.  Recover from Sex/Gender labels or partial MRZ.
    if not votes['gender'] and not any(
        'gender' in p for p in prefixes
    ):
        g = _recover_gender(evidence_list)
        if g:
            votes['gender'][g].add(('fallback', 'text_scan'))

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
