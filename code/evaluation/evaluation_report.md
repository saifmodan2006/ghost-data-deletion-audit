# Evaluation report

Public sample evaluation: 32 requests. Expected labels are read only in this
evaluation process, after predictions are computed. Production inference does
not read sample outputs. Hidden canonical outputs are unavailable.

## Metrics

| Metric | Correct / total | Accuracy |
| --- | ---: | ---: |
| Case status | 32 / 32 | 100.00% |
| Entire case (status and every ordered step) | 12 / 32 | 37.50% |
| Exact step rows, including numbering | 118 / 195 | 60.51% |
| Positional step fields | 981 / 1365 | 71.87% |
| Entire ordered step sequence | 12 / 32 | 37.50% |
| Custom regression tests | 32 / 32 | 100.00% |

Exact row accuracy uses multiset intersection of all seven fields, divided by
the sum of max(predicted step count, expected step count) per case. Field
accuracy compares the seven required fields at each array position; missing
and additional positions count as seven errors. Sequence accuracy requires
identical complete arrays. Missing an early step can lower both row and field
scores even when later actions are semantically correct. These are local
definitions, not a claim about the hidden grader's scoring formula.

Per-field correct counts: {"evidence_id": 160, "operation": 128, "phase": 160, "resource_id": 120, "state": 130, "step_no": 163, "system_id": 120}.

Schema/ordering/evidence-date validation errors: 0.
All 94 manifest files were opened and processed, producing
2902 normalized observations. An empty scoped SQL capture
can legitimately yield no positive row observations; it still supplies absence
scope. Business documents without a resolvable resource ID are read but do not
produce invented resource identifiers.

## Independent cases

These fixtures are authored independently of contest labels. Each test creates
a temporary participant-shaped dataset; no contest case IDs or expected rows
are embedded in the predictor.

| Test | Input scenario | Expected behavior |
| --- | --- | --- |
| Non-deletion authorization | A user requests only a marketing opt-out, data copy, or correction. | Do not authorize account deletion. |
| Multilingual requests | Deletion requests in Spanish, Portuguese, French, Japanese, and Korean. | Recognize deletion intent in each language. |
| Historical email and decoy | A stored search record uses OLD@example.invalid; a neighboring record uses old.extra@example.invalid. | Delete only the exact historical-email match. |
| Audit cutoff | An account is absent before cutoff; a later snapshot reports it present. | Use the earlier evidence and ignore the future snapshot. |
| Safe dependency order | An account remains with an enabled connector and restorable backup. | Disable connector, block restore, then delete account. |
| Retention | A security audit record holds the stable internal subject reference. | Preserve the record and verify it exists. |
| Compliant tombstone | A deleted-account reference keeps user_id with null name/email/phone/hash. | Verify redaction; preserve stable reference. |
| Exposed tombstone | A deleted-account reference still stores the historical email. | Report exposure, redact fields, then verify. |
| Shared conversation | A support message includes the subject email and shared order context. | Redact identifying fields; preserve conversation. |
| Replication drift | Two simultaneous reads report absence and a surviving identifiable row. | Treat deletion as incomplete. |
| Interleaved traces | Two lookup starts and two completions are interleaved for different people. | Join by trace ID, keeping identities separate. |
| Identifier boundary | Records refer to user_101 and user_1010. | Do not treat the longer reference as a match. |
| Phone formatting | The identity phone contains spaces; the stored copy has digits and country prefix only. | Match the same phone without linking a different number. |
| Benign support text | A support message has stable subject reference and no direct identifiers. | Verify redaction without flagging ordinary delivery prose as PII. |
| Prior compliant record | An old profile was absent before the current request; a current profile has a fresh absence check. | Avoid duplicating the old resolved resource in the current plan. |
| Old surviving copy | An identifiable search copy predates the request. | Retain it in scope and require deletion. |
| Foreign owner | A different explicit user reference shares the subject name. | The foreign user reference overrides the weak name match. |
| Negated preference | The person does not want the account deleted. | Do not authorize deletion. |
| Retention exception | Do not delete security records; delete my account. | Honor account deletion while preserving security context. |
| Explicit resource schema | An unfamiliar resource ID supplies system_id and data_category CACHE_ENTRY. | Use declared category and system, without assuming ID prefixes. |
| Attributable telemetry | A telemetry record retains the internal user reference. | Require anonymization. |
| Email delivery log | A retained delivery log contains the historical recipient email. | Require redaction. |
| Future row time | The file is captured before cutoff but a row claims a later observation. | Exclude the future observation. |
| Sparse snapshot | A later snapshot at another time contains a different customer. | Do not infer the subject profile is absent from unrelated scope. |
| Successful operation claim | A delete job reports success but a later lookup returns the profile. | Prefer the readback and report incomplete. |
| Later absence | A record is present in an early readback and absent in a later one. | Use the later readback. |
| Missing profile proof | Only a retained security record is explicitly linked. | Flag MISSING_PROFILE_PROOF for review. |
| Write after readback | A synchronization claim occurs after the last compliant readback. | Flag LATER_WRITE_WITHOUT_READBACK rather than treating old proof as current. |
| Multilingual refusals | Explicit requests not to delete the account in five languages. | Do not authorize deletion. |
| Name-only support exposure | A support body names the subject but has no email or phone. | Require redaction of the identifying name. |
| Conflicting catalog claim | A catalog claims a link but the readback declares a different subject. | Preserve the foreign record and flag conflicting evidence. |
| Shared phone ambiguity | Two people have the same name and phone; an isolated copy has only that phone. | Do not assign the copy destructively; flag the ambiguous identifier. |

## Change from the previous version

The same public development set is used for both measurements. This is a
development comparison, not an unbiased estimate of hidden-set generalization.

| Metric | Previous version | Improved version |
| --- | ---: | ---: |
| Status accuracy | 32/32 (100.00%) | 32/32 (100.00%) |
| Exact complete plans | 11/32 (34.38%) | 12/32 (37.50%) |
| Exact step rows | 116/197 (58.88%) | 118/195 (60.51%) |
| Positional fields | 973/1379 (70.56%) | 981/1365 (71.87%) |
| Independent tests | 12/12 | 32/32 |

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

### case_03

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_9406", "ANONYMIZED", "evidence_94"]]`

### case_04

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_004", "ABSENT", "evidence_54"]]`

### case_07

Additional: `[["FINDING", "REPORT_REMAINING_RECORD", "object_storage", "object_19", "PRESENT", "evidence_46"], ["REMEDIATION", "DELETE_RECORD", "object_storage", "object_19", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_ABSENT", "object_storage", "object_19", "ABSENT", ""]]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_007", "ABSENT", ""]]`

### case_08

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_008", "ABSENT", ""]]`

### case_09

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_3960", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_4902", "PRESENT", ""]]`

### case_10

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_010", "ABSENT", ""]]`

### case_18

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_5521", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_6645", "PRESENT", ""]]`

### case_20

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_5037", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_5569", "PRESENT", ""]]`

### case_21

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_6440", "ABSENT", "evidence_92"], ["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_5335", "ANONYMIZED", "evidence_92"]]`

### case_22

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_4990", "ABSENT", ""]]`

### case_23

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_410", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_4128", "PRESENT", ""]]`

### case_24

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_7095", "PRESENT", ""]]`

### case_25

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_3136", "ABSENT", "evidence_92"], ["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_1895", "ANONYMIZED", "evidence_92"]]`

### case_26

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_5684", "ABSENT", "evidence_92"], ["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_4566", "ANONYMIZED", "evidence_92"]]`

### case_27

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_3866", "ABSENT", "evidence_92"], ["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_4574", "ANONYMIZED", "evidence_92"]]`

### case_28

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_5482", "ABSENT", "evidence_92"], ["VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "analytics_platform", "analytics_6077", "ANONYMIZED", "evidence_92"]]`

### case_29

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_7012", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_3954", "PRESENT", ""]]`

### case_30

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_4163", "ABSENT", ""], ["VERIFICATION", "VERIFY_RECORD_PRESENT", "security_service", "audit_record_1707", "PRESENT", ""]]`

### case_31

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_4857", "ABSENT", "evidence_51"]]`

### case_32

Additional: `[]`

Missing: `[["VERIFICATION", "VERIFY_RECORD_ABSENT", "account_service", "account_8858", "ABSENT", ""]]`

## Regression execution

```text
test_benign_support_text_is_not_pii (test_audit.AuditTests.test_benign_support_text_is_not_pii) ... ok
test_catalog_claim_cannot_override_foreign_subject (test_audit.AuditTests.test_catalog_claim_cannot_override_foreign_subject) ... ok
test_cutoff_excludes_future_evidence (test_audit.AuditTests.test_cutoff_excludes_future_evidence) ... ok
test_email_delivery_redaction (test_audit.AuditTests.test_email_delivery_redaction) ... ok
test_explicit_category_and_system_fields (test_audit.AuditTests.test_explicit_category_and_system_fields) ... ok
test_explicit_foreign_subject_overrides_shared_name (test_audit.AuditTests.test_explicit_foreign_subject_overrides_shared_name) ... ok
test_flows_and_restore_before_deletion (test_audit.AuditTests.test_flows_and_restore_before_deletion) ... ok
test_historical_email_and_decoy (test_audit.AuditTests.test_historical_email_and_decoy) ... ok
test_interleaved_trace_identity (test_audit.AuditTests.test_interleaved_trace_identity) ... ok
test_later_readback_beats_earlier_presence (test_audit.AuditTests.test_later_readback_beats_earlier_presence) ... ok
test_later_write_invalidates_proof_confidence (test_audit.AuditTests.test_later_write_invalidates_proof_confidence) ... ok
test_missing_profile_is_flagged_for_review (test_audit.AuditTests.test_missing_profile_is_flagged_for_review) ... ok
test_multilingual_deletion (test_audit.AuditTests.test_multilingual_deletion) ... ok
test_multilingual_negative_requests (test_audit.AuditTests.test_multilingual_negative_requests) ... ok
test_name_in_support_body_requires_redaction (test_audit.AuditTests.test_name_in_support_body_requires_redaction) ... ok
test_negated_account_preferences (test_audit.AuditTests.test_negated_account_preferences) ... ok
test_non_deletion_requests (test_audit.AuditTests.test_non_deletion_requests) ... ok
test_old_surviving_record_still_requires_remediation (test_audit.AuditTests.test_old_surviving_record_still_requires_remediation) ... ok
test_phone_format_is_normalized (test_audit.AuditTests.test_phone_format_is_normalized) ... ok
test_prior_compliant_resource_not_repeated (test_audit.AuditTests.test_prior_compliant_resource_not_repeated) ... ok
test_replica_survival_beats_absence (test_audit.AuditTests.test_replica_survival_beats_absence) ... ok
test_retained_record_survives (test_audit.AuditTests.test_retained_record_survives) ... ok
test_retention_exception_keeps_account_authorization (test_audit.AuditTests.test_retention_exception_keeps_account_authorization) ... ok
test_row_observed_after_cutoff_is_excluded (test_audit.AuditTests.test_row_observed_after_cutoff_is_excluded) ... ok
test_shared_phone_alone_is_not_unique_identity (test_audit.AuditTests.test_shared_phone_alone_is_not_unique_identity) ... ok
test_shared_support_is_redacted (test_audit.AuditTests.test_shared_support_is_redacted) ... ok
test_sparse_later_snapshot_does_not_prove_absence (test_audit.AuditTests.test_sparse_later_snapshot_does_not_prove_absence) ... ok
test_successful_operation_claim_does_not_override_readback (test_audit.AuditTests.test_successful_operation_claim_does_not_override_readback) ... ok
test_telemetry_stable_subject_is_attributable (test_audit.AuditTests.test_telemetry_stable_subject_is_attributable) ... ok
test_tombstone_direct_identifier_requires_redaction (test_audit.AuditTests.test_tombstone_direct_identifier_requires_redaction) ... ok
test_tombstone_stable_reference_is_permitted (test_audit.AuditTests.test_tombstone_stable_reference_is_permitted) ... ok
test_user_reference_boundary (test_audit.AuditTests.test_user_reference_boundary) ... ok

----------------------------------------------------------------------
Ran 32 tests in 0.477s

OK
```

## Final full-dataset validation

Processed 518 requests in 3.802 seconds with 0 output-contract errors. 342 authorized cases require evidence review; see coverage_report.md for all case IDs and reasons. No hidden-set semantic accuracy is claimed.

## Clean extraction reproducibility and gate check

A separate cache-free OCR run read all supplied media and produced a byte-identical 518-row CSV (SHA-256 `20b4c33a1291e761130ab5d32b60bededf741bd85bc01d4c2725f268d098ef16`). It made 11 image-pipeline calls: 11 detection, 163 orientation-classification batches, and 163 recognition batches. The final recorded cached run took 3.802 seconds and made zero model calls. 0 full-dataset plans changed from the previous version; hidden correctness is not measured.

An end-to-end strict-proof CLI probe returned nonzero for unresolved evidence and preserved a pre-existing output sentinel. All 32 independent tests passed.
