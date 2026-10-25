"""Validate deliverables and create a minimal, reproducible code ZIP."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
from audit import read_csv
from validate import validate

def main():
    root=Path(__file__).resolve().parents[1]
    required=['code/README.md','code/evaluation/evaluation_report.md','code/evaluation/usage_report.md','output.csv','log.txt']
    for name in required:
        if not (root/name).is_file():raise FileNotFoundError(name)
    errors=validate(read_csv(root/'output.csv'),read_csv(root/'dataset/deletion_requests.csv'),read_csv(root/'dataset/evidence_files.csv'))
    if errors:raise ValueError(errors)
    output=root/'code.zip'
    files=sorted(p for p in (root/'code').rglob('*') if p.is_file() and p.suffix in ('.py','.md','.txt') and '__pycache__' not in p.parts)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        archive.write(root/'code/README.md','README.md')
        for path in files:archive.write(path,path.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as archive:
        bad=archive.testzip()
        if bad:raise ValueError('Corrupt ZIP member '+bad)
        names=archive.namelist()
        if any(any(part in name.split('/') for part in ('dataset','.venv','__pycache__','node_modules')) for name in names):raise ValueError('Unexpected archive content')
        if any(Path(name).suffix in ('.zip','.gz','.tar','.7z','.rar') for name in names):raise ValueError('Nested archive')
        if 'code/evaluation/evaluation_report.md' not in names or 'code/evaluation/usage_report.md' not in names:raise ValueError('Missing reports')
    manifest=[]
    for name in ('code.zip','output.csv','log.txt'):
        path=root/name
        manifest.append(dict(file=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (root/'submission_manifest.md').write_text('# Submission files\n\n| File | Bytes | SHA-256 |\n| --- | ---: | --- |\n'+''.join(f"| {item['file']} | {item['bytes']} | `{item['sha256']}` |\n" for item in manifest),encoding='utf-8')
    print(json.dumps(dict(files=manifest,code_archive_members=len(names)),indent=2))

if __name__=='__main__':main()
