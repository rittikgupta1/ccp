---
title: "Weekend SLA drops 15% in Bangalore"
date: 2026-05-05
author: ritik
team: data
type: analysis
trust: draft
expires: 2026-08-03
---

# Weekend SLA drops 15% in Bangalore

Weekend SLA dropped from 92% to 78% in Bangalore Zone 3. Root cause: rider shortage on Sundays.

## Key Findings
- Zone 3 worst performer
- Sunday drop correlates with rider unavailability
- Pre-positioning by Thursday night could mitigate

## SQL Query
```sql
SELECT hood_id, day_of_week, AVG(sla_pct) as avg_sla
FROM main.gold.aa_job_master
WHERE city = 'Bangalore'
GROUP BY hood_id, day_of_week
ORDER BY avg_sla ASC
```
