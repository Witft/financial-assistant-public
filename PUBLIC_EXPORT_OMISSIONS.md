# Exclusions and verification boundaries

No Git history, private runtime material, prototype outputs, production configuration, private original gold corpus, or live traces are included in this public candidate.

## Evaluation corpus

The private original gold corpus is excluded rather than transformed or renamed for this candidate. The public evaluation inputs are 23 newly authored deterministic synthetic cases in `evals/bill-classification-v1/`, with explicit per-row synthetic/public provenance and a self-contained generator. `SYNTHETIC_CORPUS.md` documents the public corpus contract and regeneration checks.

The evaluation-corpus replacement was historically verified under fresh isolation: the backend suite recorded **167 passed, 1 warning**, and the evaluation recorded 23 synthetic cases with no failures. Older **169 passed / 29 cases** records are historical evidence only; neither result is a current aggregate test total. A separate earlier full PostgreSQL backend lane recorded **205 passed, 1 warning**; it is likewise historical and distinct from the eval-corpus verification.

## Reports and release status

Evaluation reports are local diagnostic postprocess artifacts generated after the evaluation run. They are not live traces, do not establish online-model behavior, and do not substitute for a payload review.

This evaluation verification did not cover browser, live database, live-provider, frontend, release archives, or final public-payload review. Separate current browser evidence records two consecutive isolated real-PostgreSQL browser runs passing with real XLS upload, parse-returned persisted-ID correction, reload, backend restart, direct database verification, and no-mock guards. That evidence is limited to the recorded working-tree snapshot; it does not grant publication clearance, establish production readiness, or prove live-provider behavior.
