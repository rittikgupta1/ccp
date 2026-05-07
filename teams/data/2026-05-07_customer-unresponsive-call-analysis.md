---
title: "Customer Unresponsive Call Analysis"
date: 2026-05-07
author: ritikguptasnabbit
team: data
type: analysis
trust: draft
expires: 2026-08-05
---

# Customer Unresponsive Call Analysis

# Customer Unresponsive Call Analysis

**Period:** Apr 7 - May 6, 2026
**Window:** plus/minus 1hr of cancellation time
**Sources:** aa_job_master, bronze.exotel.calls, bronze.public.user, Mixpanel Snabbit-Expert

## Key Tables and Joins

- **Jobs:** `main.gold.aa_job_master` - filter `status = 'CANCELLED'`, `cancellation_initiated_by = 'Snabbit'`, `cancellation_reason IN ('Customer Unresponsive', 'customer_unresponsive')`
- **Phone lookup:** `bronze.public.user` - join on `customer_id = user.id` for customer phone, `last_runner_id = user.id` for runner phone
- **Calls:** `bronze.exotel.calls` - match on `CONCAT('0', user.phone)` to Exotel `To`/`From` (Exotel uses 11-digit with leading 0, user table has 10-digit)
- **Mixpanel:** project 3999241 (Snabbit-Expert) - events `arrival_call_customer_cta_click`, `arrival_chat_customer_cta_click` with properties `job_id`, `runner_id`, `customer_id`

## Critical Field: last_runner_id vs runner_id

- `runner_id` is populated for only 132 / 9,001 unresponsive jobs (1.5%)
- `last_runner_id` is populated for 8,947 / 9,001 (99.4%)
- Always use `last_runner_id` for the last allocated runner on cancelled jobs

## Timezone Note

- `cancelled_at` in aa_job_master is stored as IST despite the Z suffix in timestamp format
- Exotel `StartTime` is also IST
- No timezone conversion needed - direct comparison works

## Coverage (plus/minus 1hr of cancellation)

- Total Unresponsive Jobs: 9,001
- Jobs with CX Exotel Calls: 8,327 (92.5%)
- Jobs with Runner Exotel Calls (last_runner_id): 8,302 (92.8%)

## Customer Call Breakdown

- completed inbound before cancel: 24,234 calls (7,228 jobs, avg 43s)
- failed outbound before cancel: 4,967 calls (2,683 jobs, avg 23s)
- completed inbound after cancel: 3,646 calls (1,784 jobs, avg 31s)
- no-answer outbound before cancel: 2,666 calls (1,697 jobs, avg 38s)
- completed outbound before cancel: 1,846 calls (1,118 jobs, avg 46s)

## Runner/Expert Call Breakdown (via last_runner_id)

- completed inbound before cancel: 25,140 calls (7,315 jobs, avg 42s)
- completed inbound after cancel: 5,591 calls (3,003 jobs, avg 51s)
- completed outbound before cancel: 3,327 calls (1,714 jobs, avg 71s)
- no-answer outbound before cancel: 1,725 calls (998 jobs, avg 31s)

## Key Insights

1. Inbound calls dominate - most calls are customer/runner calling Snabbit, not outbound
2. 51% of outbound calls to customer FAIL before ringing - telephony issues
3. Runner calls are very active (comparable to customer volume) when using last_runner_id
4. 25K CTA clicks/day but only 300 unresponsive cancels/day = 1.2% conversion to cancel
5. Phone format: user table = 10 digits, Exotel = 11 digits with leading 0
6. DoD: consistently 4.4-5.9% of daily cancellations, around 5%, 280-360 jobs/day

## Mixpanel CTA Events

- arrival_call_customer_cta_click: 25K/day (started tracking Apr 28)
- arrival_chat_customer_cta_click: started May 5-6, very new
- Top-of-funnel: expert taps CTA in app then Exotel call initiated

## Excel Output

Full analysis saved to: ~/Downloads/cx_unresponsive_call_analysis.xlsx
Sheets: Summary, Mixpanel CTA Events, Sample Cases, Verification Queries, Key Findings

