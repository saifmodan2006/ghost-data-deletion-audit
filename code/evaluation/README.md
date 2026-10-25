Evaluation is isolated from inference. `main.py` in this folder reads the public
sample labels only after producing predictions through `Auditor.audit`.
The production entry point never imports this folder or opens sample outputs.

`test_audit.py` creates independent temporary datasets and runs adversarial checks.
`metrics.py` defines exact case, status, row, field, and ordered sequence metrics.
The reports are generated directly as Markdown, including every known mismatch.
