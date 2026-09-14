"""Untrusted image/PDF work runs only in a bounded child process. No network APIs."""
import io, re, warnings
from PIL import Image, ImageOps, ImageStat
import pypdfium2 as pdfium
import pytesseract
from .mrz import candidates
from .fields import FIELDS
Image.MAX_IMAGE_PIXELS = 24_000_000
warnings.simplefilter('error',Image.DecompressionBombWarning)
MAX_PAGES = 12
class DocumentError(Exception): pass

def pages_from(data, kind):
    if kind=='pdf':
        try: pdf=pdfium.PdfDocument(data)
        except Exception: raise DocumentError('PDF_CORRUPT_OR_PASSWORD')
        try:
            if len(pdf)>MAX_PAGES: raise DocumentError('TOO_MANY_PAGES')
            for i in range(len(pdf)):
                page=pdf[i]
                w,h=page.get_size()
                if w<=0 or h<=0: raise DocumentError('INVALID_PAGE_SIZE')
                scale=min(2.5,3000/max(w,h))
                bitmap=page.render(scale=scale)
                im=bitmap.to_pil().convert('RGB'); bitmap.close(); page.close()
                yield im
        finally: pdf.close()
    else:
        try:
            with Image.open(io.BytesIO(data)) as src:
                if src.format not in ('JPEG','PNG'): raise DocumentError('UNSUPPORTED_IMAGE')
                if getattr(src,'n_frames',1)>1: raise DocumentError('ANIMATED_IMAGE')
                src.load(); yield ImageOps.exif_transpose(src).convert('RGB')
        except DocumentError: raise
        except Exception: raise DocumentError('CORRUPT_OR_OVERSIZED_IMAGE')

LABELS = {
 'passport_number':r'passport\s*(?:no\.?|number)', 'full_name':r'full\s*name',
 'dob':r'date\s*of\s*birth', 'gender':r'(?:sex|gender)', 'nationality':r'nationality',
 'place_of_birth':r'place\s*of\s*birth','date_of_issue':r'date\s*of\s*issue',
 'date_of_expiry':r'date\s*of\s*expiry','place_of_issue':r'place\s*of\s*issue',
 'father_name':r"(?:father(?:'s)?\s*name|name\s*of\s*father)",
 'mother_name':r"(?:mother(?:'s)?\s*name|name\s*of\s*mother)",
 'spouse_name':r"(?:spouse(?:'s)?\s*name|name\s*of\s*spouse)", 'address':r'address', 'surname':r'surname', 'given_names':r'given\s*names?'}
def label_fields(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    out={}
    def is_label(line):
        return any(re.fullmatch(pattern+r"\s*[:/ -]*",line,re.I) for pattern in LABELS.values())
    for i,line in enumerate(lines):
        for field,pattern in LABELS.items():
            inline=re.fullmatch(pattern+r"\s*[:\-]\s*(.+)",line,re.I)
            if inline:
                out.setdefault(field,inline.group(1).strip())
            elif re.fullmatch(pattern+r"\s*[:/ -]*",line,re.I) and i+1<len(lines) and not is_label(lines[i+1]):
                value=lines[i+1]
                if field=='address':
                    for extra in lines[i+2:i+5]:
                        if is_label(extra) or '<' in extra: break
                        value+=' '+extra
                out.setdefault(field,value)
    if not out.get('full_name') and (out.get('surname') or out.get('given_names')):
        out['full_name']=' '.join((out.get('given_names','')+' '+out.get('surname','')).split())
    return {k:v for k,v in out.items() if k in FIELDS}

def extract(sources, language='eng'):
    if language not in ('eng','eng+hin','eng+ara'): raise DocumentError('UNSUPPORTED_LANGUAGE')
    fields={f:'' for f in FIELDS}; evidence=[]; previews=[]; mrzs=[]; issues=[]
    for data,kind in sources:
        for image in pages_from(data,kind):
            if len(previews)>=MAX_PAGES: raise DocumentError('TOO_MANY_PAGES')
            image.thumbnail((3000,3000))
            try:
                osd=pytesseract.image_to_osd(image,output_type=pytesseract.Output.DICT,timeout=15)
                if osd.get('rotate'): image=image.rotate(-osd['rotate'],expand=True)
            except (pytesseract.TesseractError,RuntimeError): pass
            gray=ImageOps.grayscale(image)
            if min(image.size)<600: issues.append('Low-resolution page; rescan may be needed.')
            if ImageStat.Stat(gray).stddev[0]<25: issues.append('Low contrast; inspect page readability.')
            try:
                tsv=pytesseract.image_to_data(image,lang=language,config='--psm 6',output_type=pytesseract.Output.DICT,timeout=75)
                text=pytesseract.image_to_string(image,lang=language,config='--psm 3',timeout=75)
                crop=image.crop((0,int(image.height*.55),image.width,image.height))
                raw=pytesseract.image_to_string(crop,lang='eng',config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<',timeout=45)
            except RuntimeError: raise DocumentError('OCR_TIMEOUT')
            except pytesseract.TesseractError: raise DocumentError('OCR_ENGINE_OR_LANGUAGE_ERROR')
            words=[{'text':t,'confidence':tsv['conf'][i],'box':[tsv['left'][i],tsv['top'][i],tsv['width'][i],tsv['height'][i]]} for i,t in enumerate(tsv['text']) if t.strip()]
            number=len(previews)+1
            for field,value in label_fields(text).items():
                if not fields[field]: fields[field]=value
            for m in candidates(raw+'\n'+text):
                if m['fields']['mrz'] not in [x['fields']['mrz'] for x in mrzs]: mrzs.append(m)
            evidence.append({'page':number,'text':text,'words':words,'width':image.width,'height':image.height})
            thumb=image.copy(); thumb.thumbnail((1500,1500)); out=io.BytesIO(); thumb.save(out,format='JPEG',quality=85)
            previews.append(out.getvalue())
    if not previews: raise DocumentError('EMPTY_DOCUMENT')
    if len(mrzs)>1:
        issues.append('Multiple MRZ identities found. Split into separate passport records before approval.')
    elif mrzs:
        for k,v in mrzs[0]['fields'].items():
            if fields.get(k) and fields[k]!=v: issues.append('Printed text/MRZ conflict: '+k)
            fields[k]=v
        issues+=mrzs[0]['warnings']
        if not mrzs[0]['valid']: issues.append('MRZ check digits failed. Verify against original.')
    else: issues.append('No supported TD3 MRZ found; verify all fields manually.')
    issues.append('All extraction is provisional. Check every populated field and page grouping before approval.')
    return {'fields':fields,'evidence':evidence,'warnings':list(dict.fromkeys(issues)),'mrz_checks':mrzs[0]['checks'] if len(mrzs)==1 else {},'multiple_identities':len(mrzs)>1,'engine':'Tesseract','previews':previews}
