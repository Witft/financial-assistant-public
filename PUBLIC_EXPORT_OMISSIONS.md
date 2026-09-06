# Exclusions and verification boundaries

No Git history, private runtime material, prototype outputs, production configuration, private original gold corpus, or live traces are included in this public candidate.

## Evaluation corpus

The private original gold corpus is excluded rather than transformed or renamed for this candidate. The public evaluation inputs are 23 newly authored deterministic synthetic cases in `evals/bill-classification-v1/`, with explicit per-row synthetic/public provenance and a self-contained generator. `SYNTHETIC_CORPUS.md` documents the public corpus contract and regeneration checks.

The current corpus replacement was verified under fresh isolation: the backend suite recorded **167 passed, 1 warning**, and the evaluation recorded 23 synthetic cases with no failures. Older **169 passed / 29 cases** records are historical evidence only; they are not the result of the new public corpus verification.

## Reports and release status

Evaluation reports are local diagnostic postprocess artifacts generated after the evaluation run. They are not live traces, do not establish online-model behavior, and do not substitute for a payload review.

Browser, live database, live-provider, and final public-payload review were not performed by this verification. This candidate has **no publication clearance**.
