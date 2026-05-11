---
title: "Expert Base Cohorting & Suspension Analysis"
date: 2026-05-11
author: ritikguptasnabbit
team: data
type: query
trust: draft
expires: 2026-11-07
---

# Expert Base Cohorting & Suspension Analysis

# Expert Base Cohorting & Suspension Analysis

## Tables
- `main.analytics.expert_retention_rca_fact_rg` — Runner x week fact table with all flags
- `main.analytics.expert_retention_rca_dump_rg` — Region x cluster x week aggregated dump
- `main.analytics.expert_base_cohort_rg` — Runner x day cohort table (daily grain)

## Expert Base Cohort Hierarchy (MECE)

Expert Base (all runners with a row on ref_date, not suspended)
- Active (>=1 shift in last 15 days)
  - Baby (first_login <= 7 days ago)
    - Baby_True_Active: >=1 shift in last 2 days
    - Baby_Mid_Active: 0 shifts in last 2 days
  - Old (first_login > 7 days ago)
    - Old_True_Active: >=1 shift in last 2 days
    - Old_Mid_Active: 0 shifts in L2, >=1 shift in 3-7 days
    - Old_Risk_Active: 0 shifts in L7, >=1 shift in 8-15 days
- Inactive (0 shifts in last 15 days)
  - Inactive_Baby: first_login <= 7 days ago
  - Inactive_Old: first_login > 7 days ago

Shift = a day where is_on_leave = false in av_runner_shift_datamart

## Suspension MECE Breakdown (priority order)
1. Never Came: 0 lifetime shifts
2. Came Less: 1-7 lifetime shifts total
3. Comp App New: competitor app installed after detection (new_install=1)
4. Migrated: mode location >100km from hotspot before suspension
5. Ming Cut: >=30% of last 7 shifts had ming_eligible=false
6. Low EPH: bottom 25th percentile of jobs/hour in last 14 shift days
7. Other: none of the above

## Key Definitions
- Suspended: last row in datamart falls in that week AND last_row_date <= current_date - 7d
- Reactivated: row this week, prior week had gap >7d. If both reactivated+suspended same week, prioritize suspended
- Expert Type: FL (FL week=current), New (1-4 weeks), Repeat (5+ weeks)
- Cohort: 0-7=FL, 7-34=New, 35+=Repeat (exactly aligned)
- PT/FT: avg daily shift hours <8=PT, >=8=FT
- Winback 15+/30+: absent 15+/30+ days, came back with shift on ref_date
- Unsuspended: SUSPENDED to ACTIVE on ref_date (runner_state_history)

## Source Tables
- main.gold.av_runner_shift_datamart (primary)
- bronze.public.runner_location_partitioned (GPS pings, EWKB hex)
- main.analytics.skn_competitor_app_present_experts (competitor app)
- bronze.public.runner_state_history (suspension events)

