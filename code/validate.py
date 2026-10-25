"""Submission contract checks independent of the prediction engine."""
import json
from audit import read_csv, OPERATIONS, step_key

def validate(rows,requests,manifest):
    errors=[]
    expected=sorted(r['case_id'] for r in requests)
    if [r['case_id'] for r in rows]!=expected:errors.append('Case coverage/order differs from requests')
    by_case={r['case_id']:r for r in requests}
    evidence={r['file_id']:r for r in manifest}
    allowed={(phase,operation,state) for phase,operation,state in OPERATIONS}
    fields={'step_no','phase','system_id','resource_id','operation','state','evidence_id'}
    for row in rows:
        cid=row['case_id'];status=row['deletion_status']
        if status not in ('COMPLETE','INCOMPLETE','NOT_APPLICABLE'):errors.append(cid+': invalid status')
        try:steps=json.loads(row['steps_json'])
        except (TypeError,ValueError):errors.append(cid+': invalid JSON');continue
        if not isinstance(steps,list):errors.append(cid+': steps are not an array');continue
        if status=='NOT_APPLICABLE' and steps:errors.append(cid+': unauthorized deletion steps')
        if status!='NOT_APPLICABLE' and not steps:errors.append(cid+': missing evidence')
        for i,s in enumerate(steps,1):
            if set(s)!=fields:errors.append(cid+': wrong step schema');continue
            if s['step_no']!=i:errors.append(cid+': nonconsecutive numbering')
            if (s['phase'],s['operation'],s['state']) not in allowed:errors.append(cid+': invalid operation/state')
            if not s['resource_id'] or not s['system_id']:errors.append(cid+': missing target')
            must_cite=s['phase']=='FINDING' or status=='COMPLETE'
            if must_cite:
                if s['evidence_id'] not in evidence:errors.append(cid+': invalid evidence')
                elif evidence[s['evidence_id']]['captured_at']>by_case[cid]['audit_at']:errors.append(cid+': future evidence')
            elif s['evidence_id']!='':errors.append(cid+': future step cites evidence')
            if status=='COMPLETE' and s['phase']!='VERIFICATION':errors.append(cid+': COMPLETE includes nonverification')
        if all('operation' in s for s in steps) and steps!=sorted(steps,key=step_key):errors.append(cid+': wrong operation order')
        if status=='INCOMPLETE' and not any(s['phase']=='FINDING' for s in steps):errors.append(cid+': incomplete without findings')
    return errors
