"""CLI: python code/main.py --dataset dataset --output output.csv."""
from pathlib import Path
import argparse
import csv
import time
import json
from collections import Counter
from audit import Auditor, read_csv
from validate import validate

def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description='Audit deletion requests against local evidence')
    parser.add_argument('--dataset',type=Path,default=root/'dataset')
    parser.add_argument('--requests',default='deletion_requests.csv')
    parser.add_argument('--output',type=Path,default=root/'output.csv')
    parser.add_argument('--cache',type=Path,default=None)
    parser.add_argument('--strict-proof',action='store_true',help='Refuse to emit predictions with unresolved evidence coverage')
    args=parser.parse_args()
    start=time.perf_counter()
    auditor=Auditor(args.dataset,args.cache)
    requests=read_csv(args.dataset/args.requests)
    rows=[auditor.audit(r) for r in sorted(requests,key=lambda r:r['case_id'])]
    errors=validate(rows,requests,read_csv(args.dataset/'evidence_files.csv'))
    if errors:raise ValueError('Output validation failed: '+str(errors[:10]))
    review_cases={cid:d['review_reasons'] for cid,d in auditor.diagnostics.items() if d['needs_review']}
    if args.strict_proof and review_cases:
        (auditor.cache/'review_required.json').write_text(json.dumps(review_cases,indent=2),encoding='utf-8')
        raise SystemExit(f'{len(review_cases)} cases require evidence review; output was not overwritten. See {auditor.cache / "review_required.json"}')
    with args.output.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['case_id','deletion_status','steps_json'])
        writer.writeheader();writer.writerows(rows)
    run=dict(requests=len(rows),seconds=round(time.perf_counter()-start,3),statuses=dict(Counter(r['deletion_status'] for r in rows)),observations=len(auditor.observations),ocr_calls=auditor.ocr_calls,ocr_cache_hits=auditor.ocr_cache_hits,model_calls=dict(auditor.model_calls),cases_requiring_review=len(review_cases),extraction=auditor.extraction)
    run['command']='python code/main.py'+(' --cache '+str(args.cache) if args.cache else '')
    run_name='full_run.json' if args.requests=='deletion_requests.csv' else 'sample_run.json'
    (auditor.cache/run_name).write_text(json.dumps(run,indent=2),encoding='utf-8')
    (auditor.cache/'decisions.json').write_text(json.dumps(auditor.diagnostics,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in run.items() if k!='extraction'},indent=2))

if __name__=='__main__':main()
