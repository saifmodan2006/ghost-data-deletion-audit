"""Run public-sample evaluation, independent tests, and Markdown reporting."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import unittest
import io
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit import Auditor, read_csv
from validate import validate
from metrics import compare

CUSTOM_CASES=[
    ('Non-deletion authorization','A user requests only a marketing opt-out, data copy, or correction.','Do not authorize account deletion.'),
    ('Multilingual requests','Deletion requests in Spanish, Portuguese, French, Japanese, and Korean.','Recognize deletion intent in each language.'),
    ('Historical email and decoy','A stored search record uses OLD@example.invalid; a neighboring record uses old.extra@example.invalid.','Delete only the exact historical-email match.'),
    ('Audit cutoff','An account is absent before cutoff; a later snapshot reports it present.','Use the earlier evidence and ignore the future snapshot.'),
    ('Safe dependency order','An account remains with an enabled connector and restorable backup.','Disable connector, block restore, then delete account.'),
    ('Retention','A security audit record holds the stable internal subject reference.','Preserve the record and verify it exists.'),
    ('Compliant tombstone','A deleted-account reference keeps user_id with null name/email/phone/hash.','Verify redaction; preserve stable reference.'),
    ('Exposed tombstone','A deleted-account reference still stores the historical email.','Report exposure, redact fields, then verify.'),
    ('Shared conversation','A support message includes the subject email and shared order context.','Redact identifying fields; preserve conversation.'),
    ('Replication drift','Two simultaneous reads report absence and a surviving identifiable row.','Treat deletion as incomplete.'),
    ('Interleaved traces','Two lookup starts and two completions are interleaved for different people.','Join by trace ID, keeping identities separate.'),
    ('Identifier boundary','Records refer to user_101 and user_1010.','Do not treat the longer reference as a match.'),
    ('Phone formatting','The identity phone contains spaces; the stored copy has digits and country prefix only.','Match the same phone without linking a different number.'),
    ('Benign support text','A support message has stable subject reference and no direct identifiers.','Verify redaction without flagging ordinary delivery prose as PII.'),
    ('Prior compliant record','An old profile was absent before the current request; a current profile has a fresh absence check.','Avoid duplicating the old resolved resource in the current plan.'),
    ('Old surviving copy','An identifiable search copy predates the request.','Retain it in scope and require deletion.'),
    ('Foreign owner','A different explicit user reference shares the subject name.','The foreign user reference overrides the weak name match.'),
    ('Negated preference','The person does not want the account deleted.','Do not authorize deletion.'),
    ('Retention exception','Do not delete security records; delete my account.','Honor account deletion while preserving security context.'),
    ('Explicit resource schema','An unfamiliar resource ID supplies system_id and data_category CACHE_ENTRY.','Use declared category and system, without assuming ID prefixes.'),
    ('Attributable telemetry','A telemetry record retains the internal user reference.','Require anonymization.'),
    ('Email delivery log','A retained delivery log contains the historical recipient email.','Require redaction.'),
    ('Future row time','The file is captured before cutoff but a row claims a later observation.','Exclude the future observation.'),
    ('Sparse snapshot','A later snapshot at another time contains a different customer.','Do not infer the subject profile is absent from unrelated scope.'),
    ('Successful operation claim','A delete job reports success but a later lookup returns the profile.','Prefer the readback and report incomplete.'),
    ('Later absence','A record is present in an early readback and absent in a later one.','Use the later readback.'),
    ('Missing profile proof','Only a retained security record is explicitly linked.','Flag MISSING_PROFILE_PROOF for review.'),
    ('Write after readback','A synchronization claim occurs after the last compliant readback.','Flag LATER_WRITE_WITHOUT_READBACK rather than treating old proof as current.'),
    ('Multilingual refusals','Explicit requests not to delete the account in five languages.','Do not authorize deletion.'),
    ('Name-only support exposure','A support body names the subject but has no email or phone.','Require redaction of the identifying name.'),
    ('Conflicting catalog claim','A catalog claims a link but the readback declares a different subject.','Preserve the foreign record and flag conflicting evidence.'),
    ('Shared phone ambiguity','Two people have the same name and phone; an isolated copy has only that phone.','Do not assign the copy destructively; flag the ambiguous identifier.'),
]

def percent(a,b):return f'{100*a/b:.2f}%' if b else 'N/A'

def main():
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,default=root/'dataset')
    parser.add_argument('--run-metadata',type=Path,default=root/'.audit_cache/full_run.json')
    args=parser.parse_args()
    auditor=Auditor(args.dataset)
    requests=read_csv(args.dataset/'sample_deletion_requests.csv')
    predictions=[auditor.audit(r) for r in requests]
    references=read_csv(args.dataset/'sample_output.csv')
    metrics=compare(predictions,references)
    checks=validate(predictions,requests,read_csv(args.dataset/'evidence_files.csv'))
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_*.py')
    stream=io.StringIO()
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report=Path(__file__).parent/'evaluation_report.md'
    n=metrics['cases']
    text=f'''# Evaluation report

Public sample evaluation: {n} requests. Expected labels are read only in this
evaluation process, after predictions are computed. Production inference does
not read sample outputs. Hidden canonical outputs are unavailable.

## Metrics

| Metric | Correct / total | Accuracy |
| --- | ---: | ---: |
| Case status | {metrics['status_correct']} / {n} | {percent(metrics['status_correct'],n)} |
| Entire case (status and every ordered step) | {metrics['exact_cases']} / {n} | {percent(metrics['exact_cases'],n)} |
| Exact step rows, including numbering | {metrics['row_matches']} / {metrics['row_total']} | {percent(metrics['row_matches'],metrics['row_total'])} |
| Positional step fields | {metrics['field_matches']} / {metrics['field_total']} | {percent(metrics['field_matches'],metrics['field_total'])} |
| Entire ordered step sequence | {metrics['sequence_correct']} / {n} | {percent(metrics['sequence_correct'],n)} |
| Custom regression tests | {tests.testsRun-len(tests.failures)-len(tests.errors)} / {tests.testsRun} | {percent(tests.testsRun-len(tests.failures)-len(tests.errors),tests.testsRun)} |

Exact row accuracy uses multiset intersection of all seven fields, divided by
the sum of max(predicted step count, expected step count) per case. Field
accuracy compares the seven required fields at each array position; missing
and additional positions count as seven errors. Sequence accuracy requires
identical complete arrays. Missing an early step can lower both row and field
scores even when later actions are semantically correct. These are local
definitions, not a claim about the hidden grader's scoring formula.

Per-field correct counts: {json.dumps(metrics['per_field'],sort_keys=True)}.

Schema/ordering/evidence-date validation errors: {len(checks)}.
All {len(auditor.extraction)} manifest files were opened and processed, producing
{len(auditor.observations)} normalized observations. An empty scoped SQL capture
can legitimately yield no positive row observations; it still supplies absence
scope. Business documents without a resolvable resource ID are read but do not
produce invented resource identifiers.

## Independent cases

These fixtures are authored independently of contest labels. Each test creates
a temporary participant-shaped dataset; no contest case IDs or expected rows
are embedded in the predictor.

| Test | Input scenario | Expected behavior |
| --- | --- | --- |
'''
    for name,scenario,outcome in CUSTOM_CASES:text+=f'| {name} | {scenario} | {outcome} |\n'
    text+='''
## Change from the previous version

The same public development set is used for both measurements. This is a
development comparison, not an unbiased estimate of hidden-set generalization.

| Metric | Previous version | Improved version |
| --- | ---: | ---: |
| Status accuracy | 32/32 (100.00%) | '''+f"{metrics['status_correct']}/{n} ({percent(metrics['status_correct'],n)})"+''' |
| Exact complete plans | 11/32 (34.38%) | '''+f"{metrics['exact_cases']}/{n} ({percent(metrics['exact_cases'],n)})"+''' |
| Exact step rows | 116/197 (58.88%) | '''+f"{metrics['row_matches']}/{metrics['row_total']} ({percent(metrics['row_matches'],metrics['row_total'])})"+''' |
| Positional fields | 973/1379 (70.56%) | '''+f"{metrics['field_matches']}/{metrics['field_total']} ({percent(metrics['field_matches'],metrics['field_total'])})"+''' |
| Independent tests | 12/12 | '''+f"{tests.testsRun-len(tests.failures)-len(tests.errors)}/{tests.testsRun}"+''' |

The gain in exact plan matching is modest. Broader reliability changes include
normalized phone identifiers, explicit foreign-subject checks, benign support
text handling, stronger negation handling, explicit system/category adapters,
timestamp-specific snapshot scope, and skipping prior compliant resources
unless later writes could invalidate their state. An inverted identity index,
per-resource timelines, and cached alias reconstruction reduce repeat scans.

## Failures found and improvements

1. Different log formats initially lost identity context. Added parsers for
   key/value, structured JSON, bracketed, pipe-delimited, syslog, and quoted
   cloud-function messages; correlated starts and completions by trace ID.
2. An activity result was insufficient to establish state. Kept activity claims
   as discovery hints; current readbacks and replica snapshots establish state.
3. Whole screenshot text could mix neighboring customers. Used OCR row geometry
   and surface-specific record categories to constrain identity associations.
4. Snapshot histories carried their own system and timestamp. Honored those
   row-level fields instead of the enclosing backup service name and date.
5. Profile-only primary captures and search-primary tables initially lacked
   adapter coverage. Added schema aliases and closed-world profile lookups.
6. Negation, multilingual deletion, shared support context, and tombstone
   preservation were exercised with independent regression cases.

## Remaining limits

Status accuracy is different from complete plan accuracy. Some public sample
answers require linking an anonymous analytics row or an absent profile's
resource ID to a person without an explicit participant-visible identity edge.
The engine uses explicit current/historical identifiers and cross-resource
references; it does not derive resource IDs from case numbers or copy labels.
A narrow nearest-workflow-time fallback is used only when no directly linked
resource exists, and its use is recorded in the diagnostic output. This is a
heuristic and can misassociate concurrent jobs. An incomplete evidence graph
can omit required verification steps or lead to an optimistic COMPLETE verdict.
Operational use should require a scoped resource inventory and route missing
lineage to review. The contest's fixed status vocabulary has no UNKNOWN value.

Other differences include additional grounded records absent from a public
sample plan. Extra findings are not silently removed to fit labels. The intent
classifier is multilingual and deterministic, but uses linguistic rules; it
is not a general-purpose natural-language understanding model. OCR can miss or
misread identifiers. Conditions outside the supplied policy vocabulary require
an adapter/rule update; unknown categories fail explicitly.

No hidden-set accuracy is claimed. Improving the missing identity edges would
require source lineage or a stronger retrieval signal, rather than substituting
a language model's guess for absent evidence.

## Per-case sequence differences

Rows below omit step numbering when displaying differences, making genuine
missing/additional targets easier to inspect. Metrics above include numbering.
'''
    for cid,extra,missing in metrics['differences']:
        text+=f'\n### {cid}\n\nAdditional: `{json.dumps(extra)}`\n\nMissing: `{json.dumps(missing)}`\n'
    text+='\n## Regression execution\n\n```text\n'+stream.getvalue()+'```\n'
    report.write_text(text,encoding='utf-8')
    if args.run_metadata.exists():
        run=json.loads(args.run_metadata.read_text())
        digest=hashlib.sha256((root/'output.csv').read_bytes()).hexdigest()
        usage=f'''# Final full-dataset usage report

Run: `{run.get('command','python code/main.py')}`

Processed requests: {run['requests']}. Runtime: {run['seconds']} seconds.
Statuses: {json.dumps(run['statuses'],sort_keys=True)}.
Read all {len(run['extraction'])} evidence files. OCR pipeline image invocations: {run['ocr_calls']}.
Image OCR cache hits: {run.get('ocr_cache_hits',0)}.
Output SHA-256: `{digest}`.

Inference is local. No hosted LLM or VLM provider is called. Neural OCR uses
RapidOCR ONNX Runtime 1.4.4 with bundled PaddleOCR models. Model call counts
below count actual ONNX `InferenceSession.run` executions, including recognition
and classification batches. These are not counts of images or text tokens.

| Provider/runtime | Model | Calls | Input tokens | Output tokens | API cost (USD) |
| --- | --- | ---: | ---: | ---: | ---: |
'''
        models=['ch_PP-OCRv4_det_infer','ch_ppocr_mobile_v2.0_cls_infer','ch_PP-OCRv4_rec_infer']
        for model in models:
            calls=run.get('model_calls',{}).get(model,0)
            usage+=f'| Local ONNX Runtime / PaddleOCR | {model} | {calls} | 0 (image tensors) | 0 (OCR characters) | $0 |\n'
        calls=sum(run.get('model_calls',{}).values())
        usage+=f'''| Hosted language models | None | 0 | 0 | 0 | $0 |
| Overall | All models | {calls} | 0 | 0 | $0 |

Total language-model tokens: **0**. Average language-model tokens per request:
**0 / {run['requests']} = 0**. Input/output token accounting is not applicable
to these image models; their inputs are tensors and recognition outputs are
character probabilities, not billable language-model tokens.

Estimated billed inference cost: **$0 total**, **$0 per request**. There are no
network inference calls, API credentials, or metered provider fees. Electricity,
CPU hardware, and the coding assistant's development usage are excluded; this
report measures the full prediction run, as required by the challenge.

OCR caching uses image-content SHA-256. This final run had {run.get('ocr_cache_hits',0)}
cache hits and {run['ocr_calls']} fresh image pipeline calls. Cached OCR contains
extracted evidence, never expected case labels. The final run's actual model
calls are reported above; previously incurred preprocessing is not relabeled
as a current model call. Caches are excluded from the code ZIP. No prompts are
used at inference because the planner is a deterministic policy/rule engine.
'''
        (report.parent/'usage_report.md').write_text(usage,encoding='utf-8')
        decisions_path=args.run_metadata.parent/'decisions.json'
        if decisions_path.exists():
            decisions=json.loads(decisions_path.read_text())
            rows=read_csv(root/'output.csv')
            validation=validate(rows,read_csv(args.dataset/'deletion_requests.csv'),read_csv(args.dataset/'evidence_files.csv'))
            statuses={r['case_id']:r['deletion_status'] for r in rows}
            review={cid:d for cid,d in decisions.items() if d.get('needs_review')}
            reasons={reason:sum(reason in d.get('review_reasons',[]) for d in decisions.values()) for reason in ['MISSING_PROFILE_PROOF','TEMPORAL_IDENTITY_HEURISTIC','LATER_WRITE_WITHOUT_READBACK','ONLY_PRE_REQUEST_EVIDENCE','CONFLICTING_SUBJECT_EVIDENCE','AMBIGUOUS_SHARED_IDENTIFIER']}
            coverage=f'''# Full-dataset evidence coverage

The final run produced {len(rows)} rows, with {len(validation)} output-contract
validation errors. Status totals: {json.dumps(run['statuses'],sort_keys=True)}.
Of {len(decisions)} authorized requests, {len(review)} require evidence review.
Schema validity is separate from whether a complete deletion proof is available.

Review reasons: `{json.dumps(reasons,sort_keys=True)}`.

Use `python code/main.py --strict-proof` for an operational gate that refuses
to overwrite predictions when these evidence gaps remain. The default contest
mode emits the required fixed-status CSV and discloses the gaps here. A flagged
COMPLETE result is provisional, not a certification. No undocumented IDs or
labels are inserted to conceal missing proof. An unflagged case is also not a
guarantee that the supplied corpus contains every real-world copy.

Before certification, supply a scoped subject-to-resource inventory, negative
lookup keys for deleted profiles, pre-anonymization lineage, and fresh readbacks
after any claimed recreating write. These are evidence requirements, not API-key
or application configuration requirements.

| Case | Predicted status | Review reasons |
| --- | --- | --- |
'''
            for cid,d in sorted(review.items()):coverage+=f"| {cid} | {statuses[cid]} | {', '.join(d['review_reasons'])} |\n"
            (report.parent/'coverage_report.md').write_text(coverage,encoding='utf-8')
            with report.open('a',encoding='utf-8') as stream:
                stream.write(f"\n## Final full-dataset validation\n\nProcessed {len(rows)} requests in {run['seconds']} seconds with {len(validation)} output-contract errors. {len(review)} authorized cases require evidence review; see coverage_report.md for all case IDs and reasons. No hidden-set semantic accuracy is claimed.\n")
    print(json.dumps({k:v for k,v in metrics.items() if k!='differences'},indent=2))
    if checks or not tests.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
