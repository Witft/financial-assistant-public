# Public export evaluation manifest

This document records the public evaluation assets and their verified status. It is not a complete payload inventory and does not independently authorize publication.

## Included public evaluation assets

- `evals/bill-classification-v1/cases.jsonl` — 23 newly authored deterministic public synthetic cases.
- `evals/bill-classification-v1/cases.template.jsonl` — byte-stable companion copy of the same public synthetic cases.
- `evals/bill-classification-v1/generate_synthetic_cases.py` — self-contained generator for the public corpus.
- `evals/bill-classification-v1/SYNTHETIC_CORPUS.md` — corpus provenance, contract coverage, and regeneration guidance.

The private original gold corpus is excluded. The public cases carry explicit synthetic/public provenance and are not a renamed, transformed, or derived copy of that excluded corpus.

## Verified result and limits

Fresh credential-free, outbound-network-blocked isolation recorded **167 passed, 1 warning** for the backend suite and a 23-case synthetic evaluation with no failures. The earlier **169 passed / 29 cases** figures are historical records, not a new result for this candidate.

The generated report layer is diagnostic postprocess after an evaluation run, not a live trace. This evidence does not cover browser, live database, or live-provider behavior, and it provides **no publication clearance**.
