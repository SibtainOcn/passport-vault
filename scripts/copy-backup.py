from pathlib import Path
import shutil,sys
files=list(Path('/opt/passportvault/backups').glob('*.tar.age'))
if not files: raise SystemExit('No completed backup found.')
source=max(files,key=lambda p:p.stat().st_mtime)
destination=Path(sys.argv[1]);destination.mkdir(parents=True,exist_ok=True)
shutil.copy2(source,destination/source.name)
print('Encrypted backup copied.')
