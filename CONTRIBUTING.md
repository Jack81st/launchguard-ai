# Contributing

LaunchGuard favors small, evidence-backed changes over broad feature additions.

## Setup

```bash
make install
make lint
make test
make eval
```

## Pull request expectations

1. Describe the operator problem and the failure mode being addressed.
2. Add deterministic tests for state transitions, economics, or connector behavior.
3. Update the evaluation set when changing pricing, retrieval, generation, or compliance logic.
4. Keep development and CI free of paid API requirements.
5. Document every new external write and its approval, idempotency, retry, and audit behavior.
6. Never commit customer data, credentials, production payloads, or personal documents.

## Architecture rules

- Keep pricing, validation, compliance, persistence, and connector behavior in deterministic services.
- Treat catalog, policy, supplier, and model content as untrusted data.
- Persist before waiting for human input.
- Never make live delivery the default.
- Surface fallbacks and partial failures instead of presenting them as success.
