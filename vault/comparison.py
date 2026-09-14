from collections import Counter
from django.utils import timezone
from .fields import FIELDS, normalize
from .models import Document
from .crypto import blind, unpack

def compare(owner,sheets,selections,mapping,date_format):
    if date_format not in ('DMY','MDY'): raise ValueError('Select a date format.')
    if not isinstance(mapping,dict) or 'passport_number' not in mapping: raise ValueError('Map the Passport number column.')
    if len(mapping)<2: raise ValueError('Map at least one detail field as well as Passport number.')
    if any(f not in FIELDS or not isinstance(i,int) or isinstance(i,bool) or i<0 or i>=40 for f,i in mapping.items()): raise ValueError('Invalid column mapping.')
    if len(set(mapping.values()))!=len(mapping): raise ValueError('Each column can map to only one field.')
    if not isinstance(selections,dict) or not selections: raise ValueError('Select at least one sheet.')
    inputs=[]
    for name,header in selections.items():
        if name not in sheets or not isinstance(header,int) or isinstance(header,bool) or header<1 or header>20 or header>len(sheets[name]): raise ValueError('Invalid sheet or header row.')
        for number,values in enumerate(sheets[name][header:],start=header+1):
            if not any(str(v).strip() for v in values): continue
            raw={f:values[i] if i<len(values) else '' for f,i in mapping.items()}
            error=''
            try: passport=normalize('passport_number',raw['passport_number'])
            except ValueError: passport=''; error='Invalid passport number.'
            if not passport: error='Missing or invalid passport number.'
            inputs.append((name,number,raw,passport,error))
    if len(inputs)>5000: raise ValueError('Maximum 5000 data rows per comparison.')
    if not inputs: raise ValueError('No data rows selected.')
    counts=Counter(p for _,_,_,p,_ in inputs if p)
    index_keys={blind(p) for _,_,_,p,_ in inputs if p}
    # Materialize a consistent candidate set and its encrypted record versions.
    from django.db import transaction
    with transaction.atomic():
        docs=list(Document.objects.select_for_update().filter(owner=owner,passport_index__in=index_keys))
        pending=Document.objects.filter(owner=owner,status__in=['queued','processing','failed','review']).exists()
        candidates={}
        for d in docs:
            data=unpack(d.payload,'document:'+str(d.id))
            candidates.setdefault(d.passport_index,[]).append((d,data))
    output=[]
    for sheet,number,raw,passport,error in inputs:
        row={'sheet':sheet,'row':number,'passport_number':passport or raw['passport_number'],'status':'Invalid Row' if error else 'Not Found','reason':error,'duplicate_input':counts[passport]>1,'comparisons':{f:{'excel':v} for f,v in raw.items()}}
        if error: output.append(row); continue
        found=candidates.get(blind(passport),[])
        country=normalize('issuing_country',raw.get('issuing_country',''))
        if country: found=[x for x in found if x[1].get('fields',{}).get('issuing_country','')==country]
        if not found:
            row.update(status='Needs Review' if pending else 'Not Found',reason='Unresolved uploads exist; absence cannot yet be confirmed.' if pending else 'No record in the owner database matches the lookup key.')
        elif len(found)>1: row.update(status='Needs Review',reason='Multiple records match this key; resolve duplicates or map issuing country.')
        else:
            doc,data=found[0]; row.update(document_id=str(doc.id),revision=doc.revision)
            uncertain=doc.status!='approved'; mismatch=False
            for field,rawvalue in raw.items():
                actual=data.get('fields',{}).get(field,'')
                item={'excel':rawvalue,'passport':actual}
                try: expected=normalize(field,rawvalue,date_format)
                except ValueError:
                    item['status']='Invalid value'; uncertain=True; row['comparisons'][field]=item; continue
                if not expected or not actual: item['status']='Missing value'; uncertain=True
                elif expected==actual: item['status']='Match'
                else: item['status']='Mismatch'; mismatch=True
                row['comparisons'][field]=item
            row['status']='Needs Review' if uncertain else ('Mismatch' if mismatch else 'Match')
            row['reason']='Record or selected fields require review.' if uncertain else ('Fields differ: '+', '.join(f for f,v in row['comparisons'].items() if v.get('status')=='Mismatch') if mismatch else 'All selected fields agree.')
        output.append(row)
    return {'created':timezone.now().isoformat(),'rules_version':'1.0','date_format':date_format,'fields':list(mapping),'scope':'All current owner records; issuing country used when mapped.','warning':'Data comparison only; does not establish document authenticity. Snapshot does not update after record edits.','rows':output}
