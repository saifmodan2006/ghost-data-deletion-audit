"""Label access is confined to evaluation, never imported by prediction code."""
import json
from collections import Counter

def compare(predictions,expected):
    predicted={r['case_id']:r for r in predictions}
    status=exact=sequence=0
    matched_steps=total_steps=matched_fields=total_fields=0
    differences=[]
    fields=['step_no','phase','system_id','resource_id','operation','state','evidence_id']
    field_scores=Counter()
    for reference in expected:
        actual=predicted[reference['case_id']]
        p=json.loads(actual['steps_json']);e=json.loads(reference['steps_json'])
        status+=actual['deletion_status']==reference['deletion_status']
        sequence+=p==e
        exact+=p==e and actual['deletion_status']==reference['deletion_status']
        serialize=lambda s:json.dumps(s,sort_keys=True)
        pc=Counter(serialize(s) for s in p);ec=Counter(serialize(s) for s in e)
        matched_steps+=sum((pc&ec).values());total_steps+=max(len(p),len(e))
        for i in range(max(len(p),len(e))):
            for field in fields:
                total_fields+=1
                if i<len(p) and i<len(e) and p[i][field]==e[i][field]:
                    matched_fields+=1;field_scores[field]+=1
        if p!=e:
            sig=lambda s:(s['phase'],s['operation'],s['system_id'],s['resource_id'],s['state'],s['evidence_id'])
            differences.append((reference['case_id'],sorted(set(map(sig,p))-set(map(sig,e))),sorted(set(map(sig,e))-set(map(sig,p)))))
    return dict(cases=len(expected),status_correct=status,exact_cases=exact,sequence_correct=sequence,row_matches=matched_steps,row_total=total_steps,field_matches=matched_fields,field_total=total_fields,per_field=dict(field_scores),differences=differences)
