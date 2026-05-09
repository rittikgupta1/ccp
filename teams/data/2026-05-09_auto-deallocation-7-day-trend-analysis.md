---
title: "Auto-Deallocation 7-Day Trend Analysis"
date: 2026-05-09
author: ritikguptasnabbit
team: data
type: analysis
trust: draft
expires: 2026-08-07
---

# Auto-Deallocation 7-Day Trend Analysis

# Auto-Deallocation 7-Day Trend Analysis (May 1-8, 2026)

## Source
- Table: bronze.public.runner_job_status_history
- Filter: reason = 'AUTO_DEALLOCATE' (from_status ASSIGNED/ACCEPTED → to_status CANCELLED)
- Joined with: bronze.public.runner_job (for job_id mapping)

## Key Query
```sql
WITH all_jobs AS (
  SELECT DATE(created_at) AS dt, COUNT(DISTINCT id) AS total_jobs
  FROM bronze.public.runner_job
  WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), 7)
    AND date_add(HOUR, 5, date_add(MINUTE, 30, created_at)) <= DATE(created_at) + INTERVAL '9 hours 55 minutes'
  GROUP BY 1
),
dealloc AS (
  SELECT DATE(h.created_at) AS dt, COUNT(DISTINCT rj.job_id) AS auto_dealloc_jobs
  FROM bronze.public.runner_job_status_history h
  JOIN bronze.public.runner_job rj ON rj.id = h.runner_job_id
  WHERE h.reason = 'AUTO_DEALLOCATE'
    AND DATE(h.created_at) >= DATE_SUB(CURRENT_DATE(), 7)
    AND date_add(HOUR, 5, date_add(MINUTE, 30, h.created_at)) <= DATE(h.created_at) + INTERVAL '9 hours 55 minutes'
  GROUP BY 1
)
SELECT a.dt, a.total_jobs, COALESCE(d.auto_dealloc_jobs, 0) AS auto_dealloc_jobs,
  ROUND(COALESCE(d.auto_dealloc_jobs, 0) * 100.0 / a.total_jobs, 2) AS dealloc_pct
FROM all_jobs a LEFT JOIN dealloc d ON a.dt = d.dt ORDER BY 1
```

## Results (till 9:55 AM IST daily)

| Date | Total Runner Jobs | Auto Dealloc | % |
|------|------------------:|-------------:|------:|
| May 01 (Thu) | 10,812 | 286 | 2.65% |
| May 02 (Fri) | 10,577 | 277 | 2.62% |
| May 03 (Sat) | 11,684 | 272 | 2.33% |
| May 04 (Sun) | 10,819 | 273 | 2.52% |
| May 05 (Mon) | 10,854 | 232 | 2.14% |
| May 06 (Tue) | 11,412 | 249 | 2.18% |
| May 07 (Wed) | 11,568 | 270 | 2.33% |
| May 08 (today) | 11,108 | 168 | 1.51% |

## Finding
- Auto-deallocation trending DOWN (2.65% → 1.51% over 7 days)
- 7-day avg: ~2.40%, today at 1.51% is the lowest
- Absolute count also dropped: ~280 → 168/day

## Notes
- aa_job_master uses cancellation_reason_bucket_4 = 'Auto Cancel' but data lags (~midnight UTC refresh)
- For real-time, query bronze.public.runner_job_status_history directly with reason = 'AUTO_DEALLOCATE'
- No separate 'MANUAL_DEALLOCATE' reason exists in the data
- Other cancellation reasons: USER_CANCEL, USER_RESCHEDULE, EMERGENCY_LOGOUT, EXPERT_DENIAL, EXPERT_LATE, BEHAVIOURAL_ISSUE, NOT_REACHABLE, LATE_LOGIN, NOT_RESPONDING

