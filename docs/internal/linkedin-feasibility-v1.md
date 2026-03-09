# LinkedIn Ingestion Feasibility (V1 Optional / V1.x)

## Scope

This note defines feasible LinkedIn ingestion options for V1 and explicit criteria for enabling or deferring integration.

V1 guardrails:

- LinkedIn remains optional/manual until a safe path is selected.
- No mandatory dependency is introduced for Gmail + Telegram core loops.
- No risky automation assumptions (scraping, autonomous outbound actions).

## Feasible Ingest Options

### Option A: Official LinkedIn API path (future, conditional)

Feasibility: low for early V1, potentially viable in V1.x.

Constraints:

- Access/approval requirements may be restrictive.
- Product and policy constraints can change and require ongoing compliance work.
- Could require additional operational work (token lifecycle, failure handling).

V1 position: do not block core loops waiting for this path.

### Option B: Manual ingest artifact (recommended for V1)

Feasibility: high.

Pattern:

- User-triggered manual ingest only (for example: pasted message metadata/text or uploaded export artifact through an internal endpoint/command).
- Normalize into existing internal artifacts in Postgres.
- Reuse existing triage/draft/digest workflows after ingest.

Why this fits V1:

- Human-supervised by default.
- No always-on connector dependency.
- Keeps system architecture DB-first and modular.

### Option C: Browser automation/scraping

Feasibility: technically possible, product-risk high.

Constraints:

- Reliability risk (UI changes, anti-automation controls).
- Policy/compliance uncertainty.
- Higher maintenance burden than V1 scope allows.

V1 position: no-go.

## Current Implementation Mode (This Repo)

- `packages/connectors/src/helm_connectors/linkedin.py` stays in scaffold mode.
- Connector behavior is manual/no-op only:
  - returns provided manual payloads unchanged when explicitly supplied
  - otherwise returns an empty list and logs `linkedin_pull_stub_manual_mode`
- No scheduler assumptions, no implicit background pull loop.

## Go / No-Go Criteria For Enabling In V1

## Go (all required)

1. Ingestion path is explicitly user-triggered or policy-safe with clear approval.
2. Integration does not become a required dependency for digest/triage core loops.
3. Data contract from ingest to storage is stable and test-covered.
4. Error handling + observability are defined (structured logs, retry/no-retry rules).
5. Outbound LinkedIn actions remain approval-gated by human decision.

## No-Go (any true)

1. Requires brittle scraping or unsafe automation assumptions.
2. Requires introducing mandatory infra/ops for all V1 workflows.
3. Adds reliability risk that can degrade Gmail/Telegram loops.
4. Cannot be implemented with clear policy/compliance confidence.

## Decision For Current V1

- Keep LinkedIn as optional/V1.x.
- Allow only manual ingest scaffold in current code.
- Revisit enablement after a concrete, policy-safe ingestion path is validated.
