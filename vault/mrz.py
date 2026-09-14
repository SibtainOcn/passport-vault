import re
from datetime import datetime, date

def digit(text):
    values = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return str(sum((0 if c=='<' else values.index(c))*[7,3,1][i%3] for i,c in enumerate(text))%10)
def parse_td3(a,b):
    if len(a)!=44 or len(b)!=44 or not a.startswith('P') or not re.fullmatch('[A-Z0-9<]+',a+b): return None
    checks = {'passport':digit(b[:9])==b[9], 'dob':digit(b[13:19])==b[19], 'expiry':digit(b[21:27])==b[27], 'composite':digit(b[:10]+b[13:20]+b[21:43])==b[43]}
    if b[42]!='<': checks['optional']=digit(b[28:42])==b[42]
    names = a[5:].split('<<',1)
    surname = names[0].replace('<',' ').strip()
    given = names[1].replace('<',' ').strip() if len(names)>1 else ''
    fields = {'passport_number':b[:9].replace('<',''),'full_name':' '.join((given+' '+surname).split()),'issuing_country':a[2:5].replace('<',''),'nationality':b[10:13],'gender':b[20].replace('<','X'),'mrz':a+'\n'+b}
    warnings = ['MRZ names may be transliterated/truncated; verify printed name.']
    for field,s in [('dob',b[13:19]),('date_of_expiry',b[21:27])]:
        if not s.isdigit(): continue
        year = int(s[:2])+2000
        if field=='dob' and year>date.today().year: year-=100
        try: fields[field]=datetime.strptime(str(year)+s[2:],'%Y%m%d').date().isoformat()
        except ValueError: warnings.append('Invalid MRZ date: '+field)
    warnings.append('MRZ uses two-digit years. Verify full dates on the passport.')
    return {'fields':fields,'checks':checks,'valid':all(checks.values()),'warnings':warnings}
def candidates(text):
    lines=[re.sub(r'\s','',x.upper()) for x in text.splitlines()]
    result=[]
    for a,b in zip(lines,lines[1:]):
        parsed=parse_td3(a,b)
        if parsed and parsed['fields']['mrz'] not in [x['fields']['mrz'] for x in result]: result.append(parsed)
    return result
