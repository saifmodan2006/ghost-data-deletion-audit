# Final full-dataset usage report

Run: `python code/main.py`

Processed requests: 518. Runtime: 3.802 seconds.
Statuses: {"COMPLETE": 153, "INCOMPLETE": 355, "NOT_APPLICABLE": 10}.
Read all 94 evidence files. OCR pipeline image invocations: 0.
Image OCR cache hits: 11.
Output SHA-256: `20b4c33a1291e761130ab5d32b60bededf741bd85bc01d4c2725f268d098ef16`.

Inference is local. No hosted LLM or VLM provider is called. Neural OCR uses
RapidOCR ONNX Runtime 1.4.4 with bundled PaddleOCR models. Model call counts
below count actual ONNX `InferenceSession.run` executions, including recognition
and classification batches. These are not counts of images or text tokens.

| Provider/runtime | Model | Calls | Input tokens | Output tokens | API cost (USD) |
| --- | --- | ---: | ---: | ---: | ---: |
| Local ONNX Runtime / PaddleOCR | ch_PP-OCRv4_det_infer | 0 | 0 (image tensors) | 0 (OCR characters) | $0 |
| Local ONNX Runtime / PaddleOCR | ch_ppocr_mobile_v2.0_cls_infer | 0 | 0 (image tensors) | 0 (OCR characters) | $0 |
| Local ONNX Runtime / PaddleOCR | ch_PP-OCRv4_rec_infer | 0 | 0 (image tensors) | 0 (OCR characters) | $0 |
| Hosted language models | None | 0 | 0 | 0 | $0 |
| Overall | All models | 0 | 0 | 0 | $0 |

Total language-model tokens: **0**. Average language-model tokens per request:
**0 / 518 = 0**. Input/output token accounting is not applicable
to these image models; their inputs are tensors and recognition outputs are
character probabilities, not billable language-model tokens.

Estimated billed inference cost: **$0 total**, **$0 per request**. There are no
network inference calls, API credentials, or metered provider fees. Electricity,
CPU hardware, and the coding assistant's development usage are excluded; this
report measures the full prediction run, as required by the challenge.

OCR caching uses image-content SHA-256. This final run had 11
cache hits and 0 fresh image pipeline calls. Cached OCR contains
extracted evidence, never expected case labels. The final run's actual model
calls are reported above; previously incurred preprocessing is not relabeled
as a current model call. Caches are excluded from the code ZIP. No prompts are
used at inference because the planner is a deterministic policy/rule engine.
