"""Local multi-engine OCR for PassportVault.
Priority: valid TD3 MRZ, then EasyOCR printed text, then Tesseract fallback.
No cloud OCR APIs are used.
"""
import io, os, re, warnings, shutil
from PIL import Image, ImageOps, ImageStat, ImageEnhance, ImageFilter
import pypdfium2 as pdfium
import pytesseract

# On Windows, auto-detect standard Tesseract installation paths if not in PATH
if os.name == 'nt':
    if not shutil.which('tesseract'):
        for _candidate in [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe'),
        ]:
            if os.path.isfile(_candidate):
                pytesseract.pytesseract.tesseract_cmd = _candidate
                _tess_dir = os.path.dirname(_candidate)
                if _tess_dir not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = _tess_dir + os.pathsep + os.environ.get('PATH', '')
                break

from .mrz import candidates
from .fields import FIELDS

Image.MAX_IMAGE_PIXELS = 24_000_000
warnings.simplefilter('error', Image.DecompressionBombWarning)
MAX_PAGES = 12

class DocumentError(Exception):
    pass

_EASY_READER = None
_EASY_ERROR = None

def get_easy_reader():
    global _EASY_READER, _EASY_ERROR
    if _EASY_READER is not None:
        return _EASY_READER
    if _EASY_ERROR is not None:
        return None
    try:
        import easyocr
        _EASY_READER = easyocr.Reader(
            ['en'],
            gpu=False,
            model_storage_directory='/opt/easyocr-models',
            user_network_directory='/tmp/easyocr-user-network',
            download_enabled=False,
            verbose=False
        )
        return _EASY_READER
    except Exception as exc:
        _EASY_ERROR = f'{type(exc).__name__}: {exc}'
        return None


def easyocr_text(image):
    reader = get_easy_reader()
    if reader is None:
        return '', []
    try:
        import numpy as np
        results = reader.readtext(np.asarray(image.convert('RGB')), detail=1, paragraph=False)
    except Exception:
        return '', []
    plain, lines = [], []
    for item in results:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        box, text, confidence = item[0], str(item[1]).strip(), item[2]
        if not text:
            continue
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0
        plain.append(text)
        lines.append({'text': text, 'confidence': confidence, 'box': box})
    return '\n'.join(plain), lines



def build_ocr_variants(image):
    """Create OCR-friendly versions for small/compressed passport photos."""
    base = image.convert('RGB')
    # Passport photos shared over messaging apps are often around 400x400.
    # Upscale small pages before OCR, but cap the long edge to avoid huge memory use.
    long_edge = max(base.size)
    if long_edge < 1800:
        scale = min(4.0, 1800.0 / max(1, long_edge))
        base = base.resize(
            (max(1, int(base.width * scale)), max(1, int(base.height * scale))),
            Image.Resampling.LANCZOS,
        )

    gray = ImageOps.grayscale(base)
    contrast = ImageOps.autocontrast(gray, cutoff=1)
    contrast = ImageEnhance.Contrast(contrast).enhance(1.45)
    sharp = contrast.filter(ImageFilter.UnsharpMask(radius=1.6, percent=180, threshold=2))

    # A conservative binary variant helps MRZ and faint printed fields.
    # Threshold is based on the image mean so it adapts to bright/dim scans.
    mean = ImageStat.Stat(sharp).mean[0]
    threshold = max(145, min(205, int(mean * 0.92)))
    binary = sharp.point(lambda px: 255 if px > threshold else 0, mode='1').convert('L')

    return {
        'upscaled': base,
        'enhanced': sharp,
        'binary': binary,
    }


def combine_texts(*texts):
    out = []
    seen = set()
    for text in texts:
        for line in str(text or '').splitlines():
            line = line.strip()
            if not line:
                continue
            key = re.sub(r'\s+', ' ', line).upper()
            if key not in seen:
                seen.add(key)
                out.append(line)
    return '\n'.join(out)


def recover_mrz_like_fields(*texts):
    """Conservative fallback for OCR text when the formal TD3 parser misses a noisy MRZ."""
    joined = '\n'.join(str(t or '') for t in texts)
    upper = joined.upper()

    recovered = {}

    # Indian passport numbers are one letter followed by seven digits.
    # Require repeated OCR evidence before using the value.
    candidates_found = re.findall(r'(?<![A-Z0-9])([A-Z][0-9]{7})(?![A-Z0-9])', upper)
    if candidates_found:
        counts = {}
        for value in candidates_found:
            counts[value] = counts.get(value, 0) + 1
        best = max(counts, key=counts.get)
        if counts[best] >= 2:
            recovered['passport_number'] = best

    # Recover DOB / expiry from a noisy TD3 second line only when its structure
    # is still recognizable. We do not guess from Excel data.
    compact_lines = [
        re.sub(r'\s+', '', line.upper())
        for line in joined.splitlines()
        if line.strip()
    ]
    for line in compact_lines:
        m = re.search(
            r'([A-Z][0-9]{7})<([0-9])IND([0-9]{6})([0-9])([MFX<0O]?)([0-9]{6})([0-9])',
            line
        )
        if not m:
            continue

        pn, _pn_check, dob_raw, _dob_check, sex_raw, exp_raw, _exp_check = m.groups()
        recovered.setdefault('passport_number', pn)
        recovered.setdefault('nationality', 'INDIAN')

        def mrz_date(raw, expiry=False):
            yy, mm, dd = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
            if not (1 <= mm <= 12 and 1 <= dd <= 31):
                return ''
            if expiry:
                year = 2000 + yy
            else:
                year = 1900 + yy if yy > 40 else 2000 + yy
            return f'{dd:02d}-{mm:02d}-{year:04d}'

        dob = mrz_date(dob_raw, expiry=False)
        exp = mrz_date(exp_raw, expiry=True)
        if dob:
            recovered.setdefault('dob', dob)
        if exp:
            recovered.setdefault('date_of_expiry', exp)
        if sex_raw in ('M', 'F', 'X'):
            recovered.setdefault('gender', sex_raw)
        break

    return recovered


def tesseract_pass(image, language):
    """Run complementary Tesseract layouts and return combined text + word data."""
    texts = []
    words = []
    for psm in (6, 11):
        try:
            text = pytesseract.image_to_string(
                image, lang=language, config=f'--psm {psm}', timeout=75
            )
            if text.strip():
                texts.append(text)
            if psm == 6:
                tsv = pytesseract.image_to_data(
                    image,
                    lang=language,
                    config='--psm 6',
                    output_type=pytesseract.Output.DICT,
                    timeout=75,
                )
                words = [
                    {
                        'text': t,
                        'confidence': tsv['conf'][i],
                        'box': [
                            tsv['left'][i], tsv['top'][i],
                            tsv['width'][i], tsv['height'][i]
                        ],
                    }
                    for i, t in enumerate(tsv['text']) if t.strip()
                ]
        except RuntimeError:
            raise DocumentError('OCR_TIMEOUT')
        except pytesseract.TesseractError:
            raise DocumentError('OCR_ENGINE_OR_LANGUAGE_ERROR')
        except (pytesseract.TesseractNotFoundError, Exception):
            pass
    return combine_texts(*texts), words


def mrz_text_from_variants(variants):
    """Read the lower passport zone separately using MRZ-biased preprocessing."""
    outputs = []
    whitelist = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
    for name in ('enhanced', 'binary', 'upscaled'):
        image = variants[name]
        # Indian passport MRZ is near the bottom; include enough area for both lines.
        crop = image.crop((0, int(image.height * 0.58), image.width, image.height))
        for psm in (6, 7):
            try:
                txt = pytesseract.image_to_string(
                    crop,
                    lang='eng',
                    config=f'--psm {psm} -c tessedit_char_whitelist={whitelist}',
                    timeout=45,
                )
                if txt.strip():
                    outputs.append(txt)
            except (RuntimeError, pytesseract.TesseractError, pytesseract.TesseractNotFoundError, Exception):
                continue
    return combine_texts(*outputs)

def pages_from(data, kind):
    if kind == 'pdf':
        try:
            pdf = pdfium.PdfDocument(data)
        except Exception:
            raise DocumentError('PDF_CORRUPT_OR_PASSWORD')
        try:
            if len(pdf) > MAX_PAGES:
                raise DocumentError('TOO_MANY_PAGES')
            for i in range(len(pdf)):
                page = pdf[i]
                w, h = page.get_size()
                if w <= 0 or h <= 0:
                    raise DocumentError('INVALID_PAGE_SIZE')
                scale = min(2.5, 3000 / max(w, h))
                bitmap = page.render(scale=scale)
                im = bitmap.to_pil().convert('RGB')
                bitmap.close(); page.close()
                yield im
        finally:
            pdf.close()
    else:
        try:
            with Image.open(io.BytesIO(data)) as src:
                if src.format not in ('JPEG', 'PNG'):
                    raise DocumentError('UNSUPPORTED_IMAGE')
                if getattr(src, 'n_frames', 1) > 1:
                    raise DocumentError('ANIMATED_IMAGE')
                src.load()
                yield ImageOps.exif_transpose(src).convert('RGB')
        except DocumentError:
            raise
        except Exception:
            raise DocumentError('CORRUPT_OR_OVERSIZED_IMAGE')

LABELS = {
    'passport_number': r'passport\s*(?:no\.?|number)',
    'full_name': r'full\s*name',
    'dob': r'date\s*of\s*birth',
    'gender': r'(?:sex|gender)',
    'nationality': r'nationality',
    'place_of_birth': r'place\s*of\s*birth',
    'date_of_issue': r'date\s*of\s*issue',
    'date_of_expiry': r'date\s*of\s*expiry',
    'place_of_issue': r'place\s*of\s*issue',
    'father_name': r"(?:father(?:'s)?\s*name|name\s*of\s*father)",
    'mother_name': r"(?:mother(?:'s)?\s*name|name\s*of\s*mother)",
    'spouse_name': r"(?:spouse(?:'s)?\s*name|name\s*of\s*spouse)",
    'address': r'address',
    'surname': r'surname',
    'given_names': r'given\s*names?'
}
DATE_FIELDS = {'dob', 'date_of_issue', 'date_of_expiry'}

def clean_value(field, value):
    value = ' '.join(str(value or '').replace('\u00a0', ' ').split())
    value = re.sub(r'^[\s:;>|=/\\._-]+', '', value)
    value = re.sub(r'[\s:;>|=/\\._-]+$', '', value)
    if field == 'passport_number':
        value = re.sub(r'[^A-Za-z0-9]', '', value).upper()
    elif field in DATE_FIELDS:
        m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b', value)
        if m:
            d, mo, y = m.groups()
            if len(y) == 2:
                y = ('19' if int(y) > 40 else '20') + y
            value = f'{int(d):02d}-{int(mo):02d}-{y}'
    elif field == 'gender':
        u = value.upper()
        tokens = re.findall(r'\b(MALE|FEMALE|M|F|X)\b', u)
        if tokens:
            t = tokens[0]
            value = {'MALE': 'M', 'FEMALE': 'F'}.get(t, t)
        else:
            value = u
    elif field == 'nationality':
        value = value.upper()
    return value.strip()

def label_fields(text):
    lines = [x.strip() for x in str(text or '').splitlines() if x.strip()]
    out = {}
    def is_label(line):
        return any(re.fullmatch(pattern + r'\s*[:/>\-=._]*', line, re.I) for pattern in LABELS.values())
    for i, line in enumerate(lines):
        for field, pattern in LABELS.items():
            inline = re.fullmatch(pattern + r'\s*[:;>/=\-._]*\s*(.+)', line, re.I)
            if inline:
                val = clean_value(field, inline.group(1))
                if val:
                    out.setdefault(field, val)
                continue
            if re.fullmatch(pattern + r'\s*[:/>\-=._]*', line, re.I):
                if i + 1 < len(lines) and not is_label(lines[i + 1]):
                    value = lines[i + 1]
                    if field == 'address':
                        for extra in lines[i + 2:i + 5]:
                            if is_label(extra) or '<' in extra:
                                break
                            value += ' ' + extra
                    val = clean_value(field, value)
                    if val:
                        out.setdefault(field, val)
    if not out.get('full_name') and (out.get('surname') or out.get('given_names')):
        out['full_name'] = ' '.join((out.get('given_names', '') + ' ' + out.get('surname', '')).split())
    return {k: v for k, v in out.items() if k in FIELDS}

def norm(field, value):
    value = clean_value(field, value)
    if not value:
        return ''
    if field in {'full_name', 'father_name', 'mother_name', 'spouse_name'}:
        return re.sub(r'[^A-Z0-9]', '', value.upper())
    if field == 'nationality':
        return re.sub(r'[^A-Z]', '', value.upper())
    return value.upper()

def merge_printed_fields(easy_fields, tess_fields, issues):
    merged = {f: '' for f in FIELDS}
    for field in FIELDS:
        e = clean_value(field, easy_fields.get(field, ''))
        t = clean_value(field, tess_fields.get(field, ''))
        if e and t:
            if norm(field, e) == norm(field, t):
                merged[field] = e
            else:
                merged[field] = e
                issues.append(f'OCR disagreement for {field}: EasyOCR and Tesseract read different values.')
        elif e:
            merged[field] = e
            issues.append(f'{field} was read by EasyOCR only.')
        elif t:
            merged[field] = t
            issues.append(f'{field} was read by Tesseract only.')
    return merged

def _extract_raw(sources, language='eng'):
    if language not in ('eng', 'eng+hin', 'eng+ara'):
        raise DocumentError('UNSUPPORTED_LANGUAGE')

    fields = {f: '' for f in FIELDS}
    evidence, previews, mrzs, issues = [], [], [], []
    easy_available = get_easy_reader() is not None
    if not easy_available:
        issues.append('EasyOCR unavailable; Tesseract/MRZ fallback used.')

    for data, kind in sources:
        for image in pages_from(data, kind):
            if len(previews) >= MAX_PAGES:
                raise DocumentError('TOO_MANY_PAGES')

            original_size = image.size
            image.thumbnail((3000, 3000))

            # Orientation correction is attempted on the original page first.
            try:
                osd = pytesseract.image_to_osd(
                    image, output_type=pytesseract.Output.DICT, timeout=15
                )
                if osd.get('rotate'):
                    image = image.rotate(-osd['rotate'], expand=True)
            except (pytesseract.TesseractError, pytesseract.TesseractNotFoundError, RuntimeError, Exception):
                pass

            gray = ImageOps.grayscale(image)
            low_resolution = min(original_size) < 700
            low_contrast = ImageStat.Stat(gray).stddev[0] < 22

            variants = build_ocr_variants(image)

            # EasyOCR: enhanced image is primary; binary pass is a backup for
            # alphanumeric fields such as passport number.
            # Fast OCR trial: keep one EasyOCR pass (enhanced). The binary
            # EasyOCR pass was removed to reduce processing time; Tesseract + MRZ
            # still provide independent evidence for the five approval fields.
            easy_text_1, easy_lines_1 = easyocr_text(variants['enhanced'])
            easy_text_2, easy_lines_2 = '', []
            easy_text = easy_text_1
            easy_lines = easy_lines_1

            # Tesseract: use enhanced + binary passes and two layout modes.
            tess_text_1, tess_words = tesseract_pass(variants['enhanced'], language)
            tess_text_2, _ = tesseract_pass(variants['binary'], language)
            tess_text = combine_texts(tess_text_1, tess_text_2)

            # Parse every pass independently, then combine. This avoids losing a
            # correctly-read field just because another preprocessing pass missed it.
            easy_fields = {}
            for txt in (easy_text_1, easy_text_2, easy_text):
                for k, v in label_fields(txt).items():
                    easy_fields.setdefault(k, v)

            tess_fields = {}
            for txt in (tess_text_1, tess_text_2, tess_text):
                for k, v in label_fields(txt).items():
                    tess_fields.setdefault(k, v)

            page_fields = merge_printed_fields(easy_fields, tess_fields, issues)

            # If labels were missed by OCR, recover only high-confidence values
            # from repeated OCR evidence / recognizable MRZ structure.
            fallback_fields = recover_mrz_like_fields(easy_text, tess_text)
            for field, value in fallback_fields.items():
                if value and not page_fields.get(field):
                    page_fields[field] = value
                    issues.append(f'{field} recovered from repeated OCR/MRZ evidence.')

            for field, value in page_fields.items():
                if value and not fields.get(field):
                    fields[field] = value

            # Dedicated MRZ recovery is much more reliable than feeding the whole
            # passport page to a single generic OCR pass.
            raw_mrz = mrz_text_from_variants(variants)
            mrz_source = combine_texts(raw_mrz, tess_text, easy_text)
            for m in candidates(mrz_source):
                if m['fields']['mrz'] not in [x['fields']['mrz'] for x in mrzs]:
                    mrzs.append(m)

            # Quality notes no longer imply automatic rejection: enhancement was
            # already applied before OCR.
            if low_resolution:
                issues.append('Low-resolution source detected; enhanced OCR preprocessing was applied.')
            if low_contrast:
                issues.append('Low-contrast source detected; contrast enhancement was applied.')

            number = len(previews) + 1
            evidence.append({
                'page': number,
                'text': tess_text,
                'tesseract_text': tess_text,
                'easyocr_text': easy_text,
                'mrz_text': raw_mrz,
                'tesseract_words': tess_words,
                'easyocr_lines': easy_lines,
                'words': tess_words,
                'width': image.width,
                'height': image.height,
                'source_width': original_size[0],
                'source_height': original_size[1],
                'preprocessing': 'upscale+autocontrast+sharpen+binary',
            })

            # Preserve the original-looking preview for the UI.
            thumb = image.copy()
            thumb.thumbnail((1500, 1500))
            out = io.BytesIO()
            thumb.save(out, format='JPEG', quality=85)
            previews.append(out.getvalue())

    if not previews:
        raise DocumentError('EMPTY_DOCUMENT')

    if len(mrzs) > 1:
        issues.append('Multiple MRZ identities found. Split into separate passport records before approval.')
    elif mrzs:
        for k, v in mrzs[0]['fields'].items():
            if k not in fields:
                continue
            if fields.get(k) and v and norm(k, fields[k]) != norm(k, v):
                issues.append('Printed text/MRZ conflict: ' + k)
            if v:
                fields[k] = v
        issues += mrzs[0]['warnings']
        if not mrzs[0]['valid']:
            issues.append('MRZ check digits failed. Verify against original.')
    else:
        issues.append('No supported TD3 MRZ found; enhanced printed OCR was used.')

    issues.append('Automatic extraction is provisional; critical disagreements should be reviewed before final approval.')
    engine = 'Enhanced EasyOCR + Tesseract + MRZ' if easy_available else 'Enhanced Tesseract + MRZ'
    return {
        'fields': fields,
        'evidence': evidence,
        'warnings': list(dict.fromkeys(issues)),
        'mrz_checks': mrzs[0]['checks'] if len(mrzs) == 1 else {},
        'multiple_identities': len(mrzs) > 1,
        'engine': engine,
        'preprocessing': 'upscale+autocontrast+sharpen+binary',
        'previews': previews,
    }



def extract(sources, language='eng'):
    from .ocr_recovery import reconcile
    return reconcile(_extract_raw(sources, language))
