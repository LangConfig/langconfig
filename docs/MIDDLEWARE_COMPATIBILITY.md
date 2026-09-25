# LangChain middleware and PII compatibility

The local `AgentMiddleware` base now inherits LangChain's public middleware
base as well as `ABC`. Current agent construction reads inherited upstream
fields such as `trace_policy`; a standalone local base omitted those fields,
so ordinary agents using the default `TimestampMiddleware` could fail before
execution. Existing local middleware hooks and retry behavior are unchanged.

The regression creates a real LangChain agent with a fixture model and the
default timestamp middleware, invokes it, and checks the response. It makes
no provider request. The existing agent-factory integration tests also cover
default middleware construction.

The PII tools also stop unpacking the private `PIIMiddleware._process_content`
hook, which now returns a changed flag instead of a match list. Detection uses
the middleware's detector and `apply_strategy` directly, preserving both the
processed text and the match records used by summaries. Profile allowlists
filter matches before applying the requested redact, mask, or hash strategy.
Profile execution errors raise a tool failure instead of returning an error
string as a successful result. Missing profiles and invalid strategy messages
retain their existing behavior.

Regressions exercise detection edge cases, all three allowlisted strategies,
unchanged no-match text, and an unavailable profile database. The failure test
uses a stub session and makes no database connection.

From `backend/`, in the project's Python environment:

```console
python -m pytest tests/test_pii_tool.py tests/test_pii_edge_cases.py tests/test_middleware.py tests/integration/test_agent_factory_refactor.py -q
```

September 25 verification: **111 passed**, with Python 3.12.10 and the local
LangChain 1.4.0 environment. This is a small compatibility prerequisite for
the branch split; it does not upgrade dependency ranges or introduce the
later execution-policy/retry changes. The complete dependency refresh and
its reproducible lock still need their own validation.

This extraction resolves the 74 PII failures seen in the initial remote CI run.
The complete remote suite must run again on the updated branch. Its inherited
dependency-advisory findings remain outside this compatibility slice.
