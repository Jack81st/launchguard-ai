# Threat Model

## Protected assets

- Shopify Admin API credentials;
- product and supplier evidence;
- pricing assumptions and margins;
- reviewer identity and decisions;
- delivery idempotency records;
- generated product content.

## Primary threats and controls

| Threat | Current control | Remaining work |
|---|---|---|
| Prompt injection in supplier or policy text | Strict data boundaries, pattern screening, deterministic default, post-generation checks | Add model-independent classifiers and document quarantine |
| Accidental publication | Dry-run default, explicit interrupt/resume approval, `DRAFT` status assertion | Add store allowlists and scoped service accounts |
| Duplicate remote products | Local ledger, deterministic handle, remote lookup | Add transactional outbox and reconciliation worker |
| Secret disclosure | Environment-only configuration, ignored `.env`, no secret logging | Use a managed secret store and automated scanning |
| Approval spoofing | Named reviewer stored in audit ledger | Add authentication, RBAC, signed sessions, and immutable audit export |
| Stale rules or FX | Effective dates, provider and rate date, visible fallback warning | Add policy owners, expiry rules, and scheduled refresh |
| HTML injection | Escaped deterministic content and executable-construct check | Add a strict HTML allowlist sanitizer |
| Partial Shopify failure | Product remains draft and the error is surfaced | Add reconciliation and operator rollback tooling |

## Out of scope for 0.1

LaunchGuard 0.1 is a single-service local deployment. It does not claim tenant isolation, regulated-data compliance, high availability, or distributed exactly-once delivery.
