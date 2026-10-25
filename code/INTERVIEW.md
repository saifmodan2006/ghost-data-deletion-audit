# Interview preparation

## Explain the solution

The problem is proof of deletion across distributed systems. A successful job
is a claim; surviving replicas, historical identifiers, and re-creation paths
can invalidate it. I first check authorization, then reconstruct identity,
retrieve evidence, evaluate its timeline, apply retention policy, and generate
an ordered auditable plan.

The only neural component is local OCR. I chose explicit policy reasoning over
generative guesses so each decision has a reproducible rule and citation.
This gives zero API inference cost and prevents prompt injection in documents
from becoming tool actions. It also limits natural-language generalization.

## Be precise about evidence

- `requested_at` starts the request; `audit_at` determines the assessment cutoff.
- Observation time and evidence capture time both matter. Future evidence is
  excluded even if it appears helpful.
- Current and historical emails/hashes/phones identify copies under old aliases.
- Similar emails and prefix-sharing internal IDs must not be conflated.
- A compliant primary does not outweigh a surviving replica at the same time.
- Retained security/legal records survive; tombstones keep stable references
  while direct identifiers are redacted.
- Sync jobs stop and unsafe restores are blocked before record remediation.

## Explain the measurements honestly

Use the actual numbers in `evaluation/evaluation_report.md`. Status accuracy
and exact plan accuracy are different. Missing a retained record verification
or an anonymous analytics association can fail exact sequence matching even
when status is right. All 518 outputs are schema-validated; hidden-case accuracy
has not been measured.

The benchmark has lineage gaps: some deleted/anonymous resources have no
explicit connection back to a subject. The solution does not copy public
labels or guess IDs from case numbering. Its narrow time-based fallback is a
heuristic, and optimistic COMPLETE results remain a real limitation. In a
production system I would require a signed, scoped inventory with immutable
subject-to-resource lineage and route missing evidence to human review.

## Likely follow-up questions

**Why not delete every matching row?** Retention and shared business context
require different treatments. Backups can remain if restoration is blocked.

**How do you avoid hallucination?** Structured observations, strict supported
operations, data-driven actions, explicit evidence IDs, cutoff filtering,
deterministic ordering, and validation. Missing information is disclosed.

**What would improve accuracy most?** Explicit identity/resource lineage,
coverage manifests for negative lookups, schema validation of extracted facts,
confidence-aware multimodal extraction, and a separately evaluated intent model.

**What is the cost?** See the final full-run usage report. There are no hosted
LLM calls or billable language-model tokens. Actual local OCR batch executions
are counted per model; CPU hardware/electricity are outside the API-cost estimate.

**How does it scale?** Evidence is ingested once per run and OCR is content-cached.
Inverted identity indexes, per-resource observation lists, cached normalized
tokens, and cached alias reconstruction avoid repeated full scans. Larger
corpora can persist these indexes with their provenance and capture-time bounds.

**What improved?** The public development set moved from 11/32 to 12/32 exact
plans while retaining 32/32 statuses. Thirty-two independent tests now cover
additional failure modes. Missing profile proof, uncertain temporal association,
and writes after a compliant readback are explicit review reasons. Strict-proof
mode refuses to overwrite output when those gaps remain.
