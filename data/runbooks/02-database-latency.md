# Runbook: Database Latency

## Symptoms

- P95 query latency increases.
- Database CPU utilization is high.
- Connection pool utilization approaches capacity.
- Request retries increase.

## Investigation

1. Confirm the affected database and incident window.
2. Inspect CPU, query latency, connection utilization, and error logs.
3. Identify the slow query and its execution plan when available.
4. Check for recent deployments, traffic changes, or resource contention.
5. Avoid concluding that CPU or connection saturation is the root
   cause without corroborating evidence.

## Candidate Remediation

Possible actions include query optimization, traffic reduction,
or a controlled increase in connection capacity when justified.

Prefer a reversible, narrowly scoped change.

Do not restart the database or terminate sessions without human approval.

## Verification

- Recheck P95 query latency and CPU utilization.
- Check connection pool usage and error rate.
- Verify that application requests recover.
- Record the results and any remaining risks.
