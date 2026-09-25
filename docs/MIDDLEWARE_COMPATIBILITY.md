# LangChain middleware compatibility

The local `AgentMiddleware` base now inherits LangChain's public middleware
base as well as `ABC`. Current agent construction reads inherited upstream
fields such as `trace_policy`; a standalone local base omitted those fields,
so ordinary agents using the default `TimestampMiddleware` could fail before
execution. Existing local middleware hooks and retry behavior are unchanged.

The regression creates a real LangChain agent with a fixture model and the
default timestamp middleware, invokes it, and checks the response. It makes
no provider request. The existing agent-factory integration tests also cover
default middleware construction.

From `backend/`, in the project's Python environment:

```console
python -m pytest tests/test_middleware.py tests/integration/test_agent_factory_refactor.py -q
```

September 25 verification: **28 passed**, with Python 3.12.10 and the local
LangChain 1.4.0 environment. This is a small compatibility prerequisite for
the branch split; it does not upgrade dependency ranges or introduce the
later execution-policy/retry changes. The complete dependency refresh and
its reproducible lock still need their own validation.
