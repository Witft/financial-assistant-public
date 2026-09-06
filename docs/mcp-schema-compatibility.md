# MCP Schema Compatibility (Historical verification rationale)

> This document records the rationale and observations from a bounded compatibility review. It is not a claim that the currently packaged candidate has passed a full MCP or release gate. Check the active payload review and current dependency environment before relying on these observations.

## Historical baseline and reviewed delta

`backend/tests/test_mcp_server.py` freezes the legacy `input_schema` AST literals from the read-only original at `bccdf654710854e96a1156fa5009bedf3910d6f7` as `ORIGINAL_INPUT_SCHEMAS`.

The advertised FastMCP schema is accepted only when it is exactly that frozen baseline plus the following additions:

| Location | Approved addition |
|---|---|
| Each tool object (`monthly_summary`, `query_transactions`, `list_months`) | Pydantic-generated `title` |
| Every existing property | Pydantic-generated `title` |
| `query_transactions.properties.category` | `default: null` |
| `query_transactions.properties.source` | `default: null` |
| `query_transactions.properties.transaction_type` | `default: null` |

The test constructs the expected schema by applying this finite, named addition map to a deep copy of the frozen baseline and then uses full dictionary equality. It does not strip, normalize, or otherwise ignore schema fields. Therefore every legacy type, description, pattern, enum, bound, required list, existing `limit.default`, property set, and tool set must remain exact; any extra field or changed value fails the test.

## Historical dispatch behavior observed through FastMCP

The dispatch tests invoke `mcp.call_tool("query_transactions", ...)`, not the Python function directly. The module's `_get` HTTP adapter is mocked, so no HTTP request can leave the process.

| Input | Observed FastMCP result | HTTP adapter result |
|---|---|---|
| `{"month": "2026-04"}` (optional keys omitted) | Accepted and dispatched | Called with `{"month": "2026-04", "limit": 50}` |
| `{"month": "2026-04", "category": null, "source": null, "transaction_type": null}` | Rejected with FastMCP `ToolError` validation errors | Not called |

`default: null` here records the Python default in the generated schema; it does **not** make the non-nullable `string`/`Literal` fields accept an explicit JSON `null`. The schema was not broadened to nullable, and omission and explicit null are intentionally documented as distinct behaviors.

## Historical direct-call compatibility

The historical review covered the direct function contract. In particular, it recorded that direct `query_transactions("2026-04")` omitted unset optional filters and that `monthly_summary("2026-13")` retained YYYY-MM-shaped direct-call forwarding behavior. This section does not make a current source-change or compatibility claim.

## Historical verification record

- RED: the former byte-for-byte legacy-schema equality failed because FastMCP adds exactly the approved metadata/default fields.
- GREEN: the approved-delta equality test plus both actual-dispatch tests passed (`3 passed`).
- A previous backend-suite record reported `169 passed, 1 warning` in a particular candidate environment. That result is historical, environment-specific, and not independently re-established by this document.
- Existing bill-classification report outputs were present in that historical environment, so `scripts/run_bill_classification_eval.py` was not run merely to overwrite them.
