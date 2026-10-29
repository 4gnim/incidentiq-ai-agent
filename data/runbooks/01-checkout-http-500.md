# Runbook: Checkout HTTP 500 Spike

## Symptoms

- Checkout HTTP 500 rate rises above its configured threshold.
- Errors appear shortly after a deployment.
- Logs may mention malformed checkout payloads or tax calculation.

## Investigation

1. Confirm the incident ID, affected service, and error-rate timeline.
2. Compare the incident start time with recent deployments.
3. Inspect error logs for the exact exception and missing fields.
4. Determine whether the deployment timing and exception provide
   corroborating evidence. Do not assume correlation proves causation.
5. Compare current error rate with the pre-incident baseline.

## Candidate Remediation

If evidence indicates a regression introduced by the latest release,
propose a rollback to the previously approved version.

Do not execute a rollback without human approval.

## Verification

- Confirm the service health check succeeds.
- Confirm HTTP 500 rate falls below the alert threshold.
- Confirm checkout requests complete successfully.
- Record the observed before-and-after metrics.

## Safety

Do not change tax rules or bypass payload validation merely to
suppress errors. Preserve logs and the audit trail.
