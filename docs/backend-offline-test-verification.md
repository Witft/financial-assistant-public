# Backend offline-test verification

## Current verified state

Fresh isolation verified the backend suite at **167 passed, 1 warning**. The run used a credential-free environment and an outbound socket-denial guard; no live API, database, network service, or provider was used. This is offline verification, not production readiness or publication clearance.

The evaluation used 23 newly authored deterministic public synthetic cases. The private original gold corpus is excluded. The current synthetic corpus is documented in [SYNTHETIC_CORPUS.md](../evals/bill-classification-v1/SYNTHETIC_CORPUS.md), including provenance labels, deterministic generation, and regeneration checks.

## Reproduction order

In an isolated backend environment with declared dependencies installed:

```bash
cd backend
python scripts/run_bill_classification_eval.py
python -m pytest tests -q
```

The evaluation command generates local diagnostic reports from the public synthetic corpus. The report layer is postprocess after the run, not a live trace. It does not establish online-model generalization, real-database behavior, or live-provider behavior.

## Historical records and remaining boundaries

Earlier **169 passed / 29 cases** results are historical evidence only. They are not a new result for the public synthetic corpus and must not be presented as current verification.

Browser E2E, live database, live-provider, final public-payload review, and any publication decision remain outside this verification. This document grants **no publication clearance**.
