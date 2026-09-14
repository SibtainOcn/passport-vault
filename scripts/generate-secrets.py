import os, secrets
from pathlib import Path
root=Path('secrets'); root.mkdir(mode=0o700,exist_ok=True)
existing=[p.name for p in root.iterdir() if p.is_file()]
expected={'master','index','django','db','admin'}
if existing:
    if not expected.issubset(set(existing)): raise SystemExit('Incomplete secrets directory: stop and restore the original keys. No keys were replaced.')
    print('Existing keys preserved.')
else:
    for name in expected:
        value=secrets.token_hex(32) if name in ('master','index') else secrets.token_hex(48)
        fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
        with os.fdopen(fd,'w') as f: f.write(value+'\n')
    print('New random keys generated. Back up using the encrypted backup action.')
# Container user can read, other host users cannot.
os.chown(root,0,0)
os.chmod(root,0o700)
for name in expected:
    os.chown(root/name,0,0)
    os.chmod(root/name,0o400)
