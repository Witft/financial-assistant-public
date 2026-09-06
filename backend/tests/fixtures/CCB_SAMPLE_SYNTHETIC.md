# Synthetic CCB XLS fixture

`ccb_sample.xls` is a **SYNTHETIC** parser test fixture. It is **not a real bank statement** and must not be represented as one.

- It is generated deterministically by `generate_ccb_sample.py`; run `python generate_ccb_sample.py` from this directory, then `python generate_ccb_sample.py --check` to confirm the checked-in binary matches the generator.
- The generator has no external dependencies and does not read any historic, private, or production bill.
- Transactions, identities, and amounts are invented test scenarios; dates are invented as well. The workbook itself begins with visible provenance markers stating that it is synthetic and that people, transaction scenarios, amounts, and dates are invented.
- One real financial-organization label is retained exactly as a public parser/classification compatibility label. It is not private data, does not identify an account holder or transaction, and is not evidence of a source transaction. This generator does not read or copy the omitted private workbook.
- The fixture intentionally covers CCB header discovery, compact dates, signed amount normalization, a note-driven investment transfer, explicit transfer summaries, refund income, and incoming-transfer income.

Do not replace this fixture with a real export. Any new fixture data must remain invented, deterministic, and visibly labelled synthetic.
