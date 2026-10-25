# Ghost Data Still Exists

Built for [HackerRank Orchestrate: Ghost Data Still Exists](https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists). The participant corpus and original challenge instructions come from the [organizer starter repository](https://github.com/interviewstreet/hackerrank-orchestrate-october26).

A local deletion-audit agent combining pretrained neural OCR, historical
identity resolution, point-in-time evidence reconstruction, policy decisions,
and deterministic remediation planning. No API key or external model service
is needed. It reads the supplied corpus; it never executes deletion actions.

## Run

Use Python 3.12. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r code/requirements.txt
.\.venv\Scripts\python.exe code/main.py
.\.venv\Scripts\python.exe code/evaluation/main.py
```

On macOS/Linux replace the virtual environment command with
`python3.12 -m venv .venv` and the Python executable with `.venv/bin/python`.

Keep the organizer's `dataset/` next to `code/`. The default output is root-level
`output.csv`, sorted lexicographically by `case_id` with exactly the required
three columns. Request count is derived from input, not hardcoded. A complete
cold run typically takes several minutes on a CPU. OCR models ship with the
RapidOCR package; no runtime model-download credentials are needed.

```powershell
.\.venv\Scripts\python.exe code/main.py --dataset dataset --requests sample_deletion_requests.csv --output sample_predictions.csv
.\.venv\Scripts\python.exe code/main.py --cache .audit_cache/final
.\.venv\Scripts\python.exe -m unittest discover -s code/evaluation -p test_*.py -v
```

The default command `python code/main.py` is the recorded final run. Use an empty
new cache directory to reproduce cold-run model usage. For a custom cache, pass
`--run-metadata <cache>/full_run.json` to evaluation. Evaluation reads run metadata and
writes `code/evaluation/evaluation_report.md` and `usage_report.md`.

## Architecture

1. **Authorization:** multilingual intent rules distinguish account deletion
   from access, correction, portability, login assistance, and marketing opt-out.
2. **Identity:** reconstruct aliases from current identities and timestamped
   email/hash/phone changes. Match exact normalized identifiers and boundaries.
3. **Evidence:** adapters open every manifest file. SQLite runs in a private
   in-memory database, with attachment/extension access denied. JSON retains
   snapshot and row-level dates. Logs join interleaved traces. PDFs use text
   extraction. Screenshots use PaddleOCR and row geometry to isolate customers.
4. **Timeline:** filter both observation and capture time by `audit_at`. Scope
   absence checks to profile snapshots. At equal time, a surviving replica wins
   over an absent or compliant primary. Workflow statuses do not prove state.
5. **Policy:** read required actions from `deletion_rules.csv`. Delete complete
   records only where required; redact shared support and tombstones; anonymize
   analytics; preserve retention records; stop connectors and block restores.
6. **Plan:** order findings, remediation, and verification by the official
   operation order, then system and resource ID. Future actions have no evidence
   citation. Completed cases contain evidence-backed verification only.
7. **Validation:** check coverage, JSON schema, allowed operations/states,
   evidence dates, sequential numbering, authorization, and exact ordering.

The AI component is neural OCR. Identity resolution and planning use explicit
symbolic rules; no generative LLM is used. This keeps inference local and
reproducible, but natural-language generalization is limited to implemented
intent rules and evidence adapters.

## Evaluation and limitations

Read the bundled evaluation report for measured public-sample status, full
case, row, field, and sequence accuracy; all mismatches are disclosed. Thirty-two
independent regression cases cover authorization, languages, identity decoys,
timestamps, retention, tombstones, support context, replicas, and trace joins.
Public sample labels are opened only by evaluation code, never by prediction.
The improved version passes 32 independent regression tests. Public development
status accuracy remains 100%; exact complete plans improve from 34.38% to 37.50%.
These are development-set measurements, not hidden-set estimates.

An absent row and an anonymized record can lose the explicit link to a person.
The engine does not manufacture that link from case/resource numbering. A
narrow temporal workflow fallback is documented and flagged. Missing lineage
can omit verification steps or make COMPLETE optimistic. Production deployment
should require explicit source inventory and review unresolved associations.
The supplied benchmark vocabulary cannot express UNKNOWN. OCR, unrecognized
request wording, and new business artifact layouts are further limitations.

Use `python code/main.py --strict-proof` to refuse output when identity coverage
or current-state proof is unresolved. This preserves any existing predictions
and lists required reviews in the cache. The default contest mode keeps the
specified three-status vocabulary; flagged COMPLETE predictions are provisional.
`evaluation/coverage_report.md` lists every flagged case and the reason.

Local diagnostics are in `.audit_cache/decisions.json` (or the selected cache):
subject IDs, selected resource states, observation/capture dates, evidence IDs,
missing profile coverage, and temporal fallback use. Extracted text and OCR
boxes are cached by file content. Caches and all data are excluded from ZIPs.
The engine indexes normalized identities and resource timelines once per run,
and scopes absence checks by both snapshot and timestamp. Explicit foreign
subject references override weak name matches. Prior compliant resources are
omitted from new plans unless a later write could have recreated their data;
older surviving copies remain in scope.

## Local browser preview

After generating predictions, run `python code/preview.py --port 8765`, then
open http://127.0.0.1:8765/ on the same computer. The preview provides live
result counts, search and status filters, review flags, phase-by-phase case
details, measured evaluation metrics, reports, and submission downloads.
It is a read-only view of local files and does not execute deletion actions.
Only the preview, result API, favicon, three report routes, and three artifact
download routes are served; the repository and evidence corpus are not web directories.
The server binds to loopback and has no external service dependency.
The optional Chrome DevTools discovery request returns an empty 204 response.
The UI adapts to phone, tablet, and desktop widths: mobile case cards, accessible
section navigation, wrapping controls, touch targets, and scrollable case dialogs.
Browser checks covered widths of 320, 390, 768, and 1440 pixels with no page-level
horizontal overflow. A Trustpilot extension request to its own domain is external
to this preview; the app neither includes nor depends on Trustpilot scripts.

## Files and submission

- `main.py`: CLI and output generation.
- `audit.py`: adapters, identity matching, timeline, policy, planning.
- `validate.py`: independent output-contract validation.
- `preview.py`: optional browser interface for existing audit results.
- `evaluation/`: executable evaluation, custom tests, metrics, Markdown reports.
- `INTERVIEW.md`: explanation and honest tradeoffs for the live interview.

From the root, run `python code/package_submission.py` to validate outputs and
create `code.zip`, including this README and all source/reports. It excludes
dataset, caches, dependencies, credentials, and nested archives. Upload the
three separate files `code.zip`, `output.csv`, and `log.txt` at:

https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

The live camera interview is a separate participant step. Review the measured
limitations before submission; no leaderboard or hidden-case score is claimed.
