import hashlib, io, json, secrets, time, uuid
from datetime import timedelta
from functools import wraps
import pyotp
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Document, Source, Page, Revision, Workbook, Report, OwnerSecurity, LoginGuard, Audit
from .crypto import seal, unseal, pack, unpack, blind
from .audit import event
from .fields import FIELDS, normalize, validate_fields
from .sandbox import run

def json_body(request):
    if len(request.body)>150000: raise ValueError('Request too large.')
    data=json.loads(request.body or '{}')
    if not isinstance(data,dict): raise ValueError('Expected an object.')
    return data

def api(methods=('GET',),auth=True):
    def decorate(fn):
        @wraps(fn)
        @require_http_methods(methods)
        def wrapped(request,*args,**kwargs):
            if auth and (not request.user.is_authenticated or not request.session.get('mfa')):
                event(request.user.pk if request.user.is_authenticated else 'anonymous','access_denied')
                return JsonResponse({'error':'Please sign in.'},status=401)
            try: return fn(request,*args,**kwargs)
            except (ValueError,TypeError,KeyError,json.JSONDecodeError):
                # A controlled validation message is returned only for ValueError.
                import sys
                exc=sys.exc_info()[1]
                message=str(exc)[:240] if isinstance(exc,ValueError) and not isinstance(exc,json.JSONDecodeError) else 'Invalid request.'
                return JsonResponse({'error':message},status=400)
            except (Document.DoesNotExist,Page.DoesNotExist,Workbook.DoesNotExist,Report.DoesNotExist):
                event(request.user.pk,'record_access_denied',kwargs.get('pk',''))
                return JsonResponse({'error':'Record not found.'},status=404)
        return wrapped
    return decorate

def home(request): return render(request,'index.html')
@api(auth=False)
def session(request):
    return JsonResponse({'authenticated':bool(request.user.is_authenticated and request.session.get('mfa')),'csrf':get_token(request),'fields':FIELDS})
@api(('POST',),auth=False)
def login(request):
    data=json_body(request)
    username=str(data.get('username',''))[:150]; password=str(data.get('password',''))[:1024]; code=str(data.get('code','')).strip()[:100]
    ok=False; limited=False
    with transaction.atomic():
        LoginGuard.objects.get_or_create(pk=1)
        guard=LoginGuard.objects.select_for_update().get(pk=1)
        if guard.locked_until and guard.locked_until>timezone.now(): limited=True
        else:
            user=authenticate(request,username=username,password=password)
            if user and OwnerSecurity.objects.filter(user=user).exists():
                security=OwnerSecurity.objects.select_for_update().get(user=user)
                totp=pyotp.TOTP(unseal(security.secret,'mfa:'+str(user.id)).decode())
                step=int(time.time())//30
                for s in (step-1,step,step+1):
                    if s>security.last_step and secrets.compare_digest(totp.at(s*30),code):
                        security.last_step=s; ok=True; break
                if not ok:
                    for i,value in enumerate(security.recovery):
                        if check_password(code,value): security.recovery.pop(i); ok=True; break
                if ok: security.save(); auth_login(request,user); request.session['mfa']=True; request.session.set_expiry(1800)
            if ok: guard.failures=0; guard.locked_until=None
            else:
                guard.failures+=1
                if guard.failures>=5: guard.locked_until=timezone.now()+timedelta(minutes=15); guard.failures=0
            guard.save()
    event(request.user.pk if ok else 'anonymous','login_success' if ok else 'login_failed')
    if limited: return JsonResponse({'error':'Login temporarily locked. Try again after 15 minutes.'},status=429)
    if not ok: return JsonResponse({'error':'Invalid username, password or authenticator/recovery code.'},status=401)
    return JsonResponse({'ok':True,'csrf':get_token(request)})
@api(('POST',))
def logout(request):
    event(request.user.pk,'logout'); auth_logout(request); return JsonResponse({'ok':True})

def document_json(d,full=False):
    obj=unpack(d.payload,'document:'+str(d.id))
    result={'id':str(d.id),'status':d.status,'created':d.created.isoformat(),'revision':d.revision,'name':obj.get('name','Passport'),'fields':obj.get('fields',{}),'warnings':obj.get('warnings',[]),'error':d.error_code,'language':obj.get('language','eng'),'verification':obj.get('verification',{})}
    if full:
        result.update(evidence=obj.get('evidence',[]),mrz_checks=obj.get('mrz_checks',{}),pages=[{'id':str(p.id),'number':p.number} for p in d.pages.order_by('number')],multiple_identities=obj.get('multiple_identities',False))
    return result
@api()
def documents(request):
    page=max(1,min(int(request.GET.get('page',1)),100000)); status=request.GET.get('status','')
    qs=Document.objects.filter(owner=request.user).order_by('created' if request.GET.get('order')=='oldest' else '-created')
    search=request.GET.get('passport','').strip()
    if search:
        qs=qs.filter(passport_index=blind(normalize('passport_number',search)))
    if status: qs=qs.filter(status=status)
    total=qs.count(); values=[document_json(d) for d in qs[(page-1)*30:page*30]]
    event(request.user.pk,'list_documents')
    counts={s:Document.objects.filter(owner=request.user,status=s).count() for s in ['queued','processing','review','approved','failed']}
    return JsonResponse({'items':values,'total':total,'counts':counts,'page':page})
@api(('POST',))
def upload(request):
    files=request.FILES.getlist('files'); language=request.POST.get('language','eng')
    if not files or len(files)>12: raise ValueError('Select 1-12 files belonging to ONE passport per upload group.')
    if language not in ('eng','eng+hin','eng+ara'): raise ValueError('Unsupported language selection.')
    if sum(f.size for f in files)>25*1024*1024: raise ValueError('One passport group must be 25 MB or less.')
    if Document.objects.filter(owner=request.user,status__in=['queued','processing']).count()>=100: raise ValueError('Queue is full (100). Wait for current uploads to finish.')
    sources=[]; digest=hashlib.sha256()
    for f in files:
        raw=f.read()
        if raw.startswith(b'%PDF-'): kind='pdf'
        elif raw.startswith(b'\x89PNG\r\n\x1a\n'): kind='png'
        elif raw.startswith(b'\xff\xd8\xff'): kind='jpg'
        else: raise ValueError('Only genuine PDF, PNG and JPEG files are accepted.')
        digest.update(hashlib.sha256(raw).digest()); sources.append((raw,kind))
    index=blind(digest.hexdigest())
    with transaction.atomic():
        # Lock the owner to serialize duplicate detection and queue admission.
        from django.contrib.auth import get_user_model
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if Document.objects.filter(owner=request.user,status__in=['queued','processing']).count()>=100: raise ValueError('Queue is full (100).')
        duplicate=Document.objects.filter(owner=request.user,content_index=index).first()
        if duplicate: return JsonResponse({'error':'This exact file group already exists.','document_id':str(duplicate.id)},status=409)
        d=Document(owner=request.user,content_index=index)
        d.payload=pack({'name':str(files[0].name)[:200],'language':language,'fields':{},'warnings':[]},'document:'+str(d.id)); d.save()
        for i,(raw,kind) in enumerate(sources):
            src=Source(document=d,order=i,kind=kind); src.data=seal(raw,'source:'+str(src.id)); src.save()
        event(request.user.pk,'upload_document',d.id)
    return JsonResponse({'id':str(d.id)},status=201)
@api()
def detail(request,pk):
    d=Document.objects.get(pk=pk,owner=request.user); event(request.user.pk,'view_document',d.id)
    return JsonResponse(document_json(d,True))
@api()
def preview(request,pk):
    p=Page.objects.select_related('document').get(pk=pk,document__owner=request.user); event(request.user.pk,'view_page',p.document_id)
    return HttpResponse(unseal(p.data,'page:'+str(p.id)),content_type='image/jpeg')
@api(('POST',))
def review(request,pk):
    body=json_body(request)
    if body.get('verified') is not True: raise ValueError('Confirm that you checked the fields and that all pages belong to one passport.')
    fields=validate_fields(body.get('fields',{}))
    with transaction.atomic():
        d=Document.objects.select_for_update().get(pk=pk,owner=request.user)
        if d.status not in ('review','approved'): raise ValueError('Wait for extraction before reviewing this record.')
        if d.revision!=body.get('revision'): return JsonResponse({'error':'Record changed. Reopen it before saving.'},status=409)
        old=unpack(d.payload,'document:'+str(d.id))
        if old.get('multiple_identities'): raise ValueError('Multiple MRZ identities detected. Delete this group and upload each passport separately.')
        Revision.objects.create(document=d,version=d.revision,data=d.payload)
        old['fields']=fields; old['reviewed_at']=timezone.now().isoformat()
        d.payload=pack(old,'document:'+str(d.id)); d.revision+=1; d.status='approved'; d.passport_index=blind(fields['passport_number']); d.save()
        event(request.user.pk,'approve_document',d.id)
    return JsonResponse({'ok':True})
@api(('POST',))
def retry(request,pk):
    with transaction.atomic():
        d=Document.objects.select_for_update().get(pk=pk,owner=request.user)
        if d.status!='failed': raise ValueError('Only failed records can be retried.')
        if d.attempts>=3: raise ValueError('Retry limit reached. Delete and upload a corrected scan.')
        d.status='queued'; d.error_code=''; d.save(); event(request.user.pk,'retry_document',d.id)
    return JsonResponse({'ok':True})
@api(('POST',))
def delete_document(request,pk):
    body=json_body(request)
    if body.get('confirm')!='DELETE': raise ValueError('Type DELETE to confirm.')
    with transaction.atomic():
        d=Document.objects.select_for_update().get(pk=pk,owner=request.user)
        if d.status=='processing': raise ValueError('Wait for processing to finish before deletion.')
        event(request.user.pk,'delete_document',d.id); d.delete()
    return JsonResponse({'ok':True,'note':'Saved report snapshots and encrypted backups have separate retention.'})
@api(('POST',))
def bulk_delete_documents(request):
    body=json_body(request)
    if body.get('confirm')!='DELETE': raise ValueError('Type DELETE to confirm bulk deletion.')
    values=body.get('ids')
    if not isinstance(values,list) or not values: raise ValueError('Select at least one passport record.')
    if len(values)>100: raise ValueError('Delete at most 100 records at a time.')
    ids=[]
    for value in values:
        try: ids.append(uuid.UUID(str(value)))
        except (ValueError,TypeError,AttributeError): raise ValueError('Invalid document selection.')
    ids=list(dict.fromkeys(ids))
    with transaction.atomic():
        docs=list(Document.objects.select_for_update().filter(owner=request.user,id__in=ids))
        if len(docs)!=len(ids): raise ValueError('One or more selected records no longer exist.')
        if any(d.status=='processing' for d in docs): raise ValueError('A selected passport is still processing. Wait for it to finish, then delete.')
        for d in docs:
            event(request.user.pk,'delete_document',d.id)
            d.delete()
    return JsonResponse({'ok':True,'deleted':len(docs),'note':'Saved report snapshots and encrypted backups have separate retention.'})

@api(('POST',))
def upload_book(request):
    f=request.FILES.get('file')
    if not f or f.size>40*1024*1024: raise ValueError('Choose a .xlsx/.csv file up to 40 MB.')
    sheets=run('sheet',(f.read(),f.name),180)
    w=Workbook(owner=request.user,name=str(f.name)[:200]); w.data=pack(sheets,'workbook:'+str(w.id)); w.save(); event(request.user.pk,'upload_workbook',w.id)
    return JsonResponse({'id':str(w.id),'sheets':{name:rows[:20] for name,rows in sheets.items()}})

@api()
def master_workbook(request):
    w=Workbook.objects.filter(owner=request.user,active=True).order_by('-created').first()
    if not w: return JsonResponse({'active':False})
    return JsonResponse({'active':True,'id':str(w.id),'name':w.name,'created':w.created.isoformat(),'config':w.config})

@api(('POST',))
def activate_master(request):
    body=json_body(request)
    w=Workbook.objects.get(pk=body.get('workbook'),owner=request.user)
    sheet=body.get('sheet'); header=body.get('header'); mapping=body.get('mapping'); date_format=body.get('date_format','DMY')
    sheets=unpack(w.data,'workbook:'+str(w.id))
    if sheet not in sheets or not isinstance(header,int) or isinstance(header,bool) or header<1 or header>20 or header>len(sheets[sheet]): raise ValueError('Invalid sheet or header row.')
    if date_format not in ('DMY','MDY'): raise ValueError('Select a date format.')
    if not isinstance(mapping,dict) or 'passport_number' not in mapping or len(mapping)<2: raise ValueError('Map Passport number and at least one detail field.')
    if any(f not in FIELDS or not isinstance(i,int) or isinstance(i,bool) or i<0 or i>=40 for f,i in mapping.items()): raise ValueError('Invalid column mapping.')
    if len(set(mapping.values()))!=len(mapping): raise ValueError('Each column can map to only one field.')
    with transaction.atomic():
        Workbook.objects.filter(owner=request.user,active=True).update(active=False)
        w.active=True; w.config={'sheet':sheet,'header':header,'mapping':mapping,'date_format':date_format}; w.save(update_fields=['active','config'])
    # Re-check already extracted records so changing the master does not require re-uploading passports.
    from .auto_verify import verify_document
    for d in Document.objects.filter(owner=request.user,status__in=['approved','review','failed'],error_code=''):
        payload=unpack(d.payload,'document:'+str(d.id))
        if not payload.get('fields'): continue
        verification,new_status=verify_document(request.user,payload.get('fields',{}),payload)
        payload['verification']=verification
        d.payload=pack(payload,'document:'+str(d.id)); d.status=new_status; d.save(update_fields=['payload','status','updated'])
    event(request.user.pk,'activate_master_workbook',w.id)
    return JsonResponse({'ok':True,'id':str(w.id),'name':w.name,'config':w.config})

@api(('POST',))
def comparison(request):
    from .comparison import compare
    body=json_body(request); w=Workbook.objects.get(pk=body.get('workbook'),owner=request.user)
    result=compare(request.user,unpack(w.data,'workbook:'+str(w.id)),body.get('sheets'),body.get('mapping'),body.get('date_format'))
    r=Report(owner=request.user); r.data=pack(result,'report:'+str(r.id)); r.save(); event(request.user.pk,'compare_workbook',r.id)
    return JsonResponse({'id':str(r.id),**result})
@api()
def reports(request):
    return JsonResponse({'items':[{'id':str(r.id),'created':r.created.isoformat()} for r in Report.objects.filter(owner=request.user).order_by('-created')[:100]]})
@api()
def report_detail(request,pk):
    r=Report.objects.get(pk=pk,owner=request.user); event(request.user.pk,'view_report',r.id)
    return JsonResponse({'id':str(r.id),**unpack(r.data,'report:'+str(r.id))})
@api()
def export(request,pk,kind):
    from .sheets import export_report
    if kind not in ('csv','xlsx'): raise ValueError('Unsupported export format.')
    r=Report.objects.get(pk=pk,owner=request.user); data,mime=export_report(unpack(r.data,'report:'+str(r.id)),kind)
    event(request.user.pk,'export_report',r.id)
    response=HttpResponse(data,content_type=mime); response['Content-Disposition']='attachment; filename="passport-comparison.'+kind+'"'
    return response
@api(('POST',))
def delete_report(request,pk):
    if json_body(request).get('confirm')!='DELETE': raise ValueError('Type DELETE to confirm.')
    r=Report.objects.get(pk=pk,owner=request.user); event(request.user.pk,'delete_report',r.id); r.delete(); return JsonResponse({'ok':True})
@api()
def audit(request):
    event(request.user.pk,'view_audit')
    return JsonResponse({'items':list(Audit.objects.order_by('-id').values('at','actor','action','target','digest')[:200])})
