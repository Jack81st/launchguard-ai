# Security Policy

## Reporting

Do not open a public issue containing credentials, store domains, customer data, or an exploitable vulnerability. Contact the repository owner privately through GitHub with a minimal reproduction and impact assessment.

## Current security posture

- Shopify delivery defaults to dry-run and creates only `DRAFT` products in live mode.
- Live mode requires an explicit reviewer decision plus store and token configuration.
- Catalog and policy inputs are validated and screened for common prompt-injection patterns.
- Model output is schema-validated and cannot cite policy IDs that were not retrieved.
- Delivery uses a deterministic handle, remote lookup, and a local receipt ledger to reduce duplication.
- Secrets are read from environment variables and excluded from version control.

LaunchGuard is an alpha project, not a certified security or compliance product. Production deployments still require authentication, role-based access, managed secrets, network controls, encrypted storage, centralized audit retention, dependency scanning, and jurisdiction-specific review.
